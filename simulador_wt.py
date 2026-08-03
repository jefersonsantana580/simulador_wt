import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Simulador WT Tratores", page_icon="🚜", layout="wide")
BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documents"

@st.cache_data
def load_rules():
    return json.loads((BASE_DIR / "regras_wt.json").read_text(encoding="utf-8"))

@st.cache_data
def read_pdf_text(pdf_path: str):
    """Lê o PDF para comprovar disponibilidade e permitir consulta textual.
    A lógica efetiva permanece estruturada no regras_wt.json, evitando decisões frágeis por OCR.
    """
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return "\n".join((page.extract_text() or "") for page in reader.pages), None
    except Exception as exc:
        return "", str(exc)

RULES = load_rules()

def clean_code(value: str) -> str:
    return "".join(str(value or "").upper().split())

def identify(code: str):
    code = clean_code(code)
    candidates = []
    for family, cfg in RULES.items():
        for prefix in cfg.get("model_prefixes", []):
            if code.startswith(prefix):
                candidates.append((len(prefix), family, prefix))
    if not candidates:
        return None
    _, family, prefix = max(candidates, key=lambda item: item[0])
    return {"family": family, "model": prefix}

def char_at(code: str, position: int) -> str:
    return code[position - 1] if len(code) >= position else ""

def analyze(current: str, proposed: str, family: str):
    cfg = RULES[family]
    rows = []
    for field in cfg["fields"]:
        pos = field["position"]
        old, new = char_at(current, pos), char_at(proposed, pos)
        same = old == new
        rows.append({
            "Posição": pos,
            "Componente": field["label"],
            "Atual": old,
            "Proposto": new,
            "Alterou?": "Não" if same else "Sim",
            "Resultado": field["action_if_equal"] if same else field["action_if_different"],
        })
    violations = []
    for rule in cfg.get("special_rules", []):
        pos = rule["position"]
        if char_at(current, pos) == rule["when_current"] and char_at(proposed, pos) != rule["required_proposed"]:
            violations.append(rule["message"])
    return rows, violations

def decode_code(code: str, family: str):
    cfg = RULES[family]
    documentation = cfg.get("documentation", {})
    value_maps = documentation.get("position_values", {})
    decoded = []
    unknown = []
    fields = {int(item["position"]): item["label"] for item in cfg["fields"]}
    for pos, label in fields.items():
        value = char_at(code, pos)
        description = value_maps.get(str(pos), {}).get(value)
        if pos == min(fields):
            description = f"Modelo {code[:pos]}"
        if not description:
            description = "Valor não documentado no PDF cadastrado"
            unknown.append(f"Posição {pos} ({label}): '{value}'")
        decoded.append({"Posição": pos, "Componente": label, "Código": value if pos != min(fields) else code[:pos], "Configuração": description})
    return decoded, unknown

def validate_documented_configuration(code: str, family: str):
    doc = RULES[family].get("documentation", {})
    alerts = []
    for restriction in doc.get("restrictions", []):
        position = restriction["position"]
        current_value = char_at(code, position)
        applies = current_value == restriction.get("value") or current_value in restriction.get("values", [])
        if not applies:
            continue
        if "required" in restriction:
            req = restriction["required"]
            if char_at(code, req["position"]) != req["value"]:
                alerts.append(restriction["message"])
        if "model_prefix" in restriction and not code.startswith(restriction["model_prefix"]):
            alerts.append(restriction["message"])
    return alerts

def pdf_status(family: str):
    doc = RULES[family].get("documentation")
    if not doc:
        return None, None, "Ainda não há PDF documental cadastrado para esta família."
    pdf_path = DOCUMENTS_DIR / doc["pdf_file"]
    if not pdf_path.exists():
        return doc, pdf_path, f"PDF não encontrado em: documentos/{doc['pdf_file']}"
    text, error = read_pdf_text(str(pdf_path))
    if error:
        return doc, pdf_path, f"PDF encontrado, mas não pôde ser lido: {error}"
    return doc, pdf_path, f"PDF encontrado e lido: {len(text)} caracteres extraídos."

st.title("🚜 Simulador WT e Decodificador de Configuração")
st.caption("Identifica a família, compara códigos, aplica as regras de WT e descreve a configuração documentada.")

left, right = st.columns(2)
with left:
    current = clean_code(st.text_input("Código atual", placeholder="Ex.: 7725KF0M0FB"))
with right:
    proposed = clean_code(st.text_input("Código proposto", placeholder="Ex.: 7725KF0K0ME"))

if current or proposed:
    id_current = identify(current) if current else None
    id_proposed = identify(proposed) if proposed else None
    c1, c2 = st.columns(2)
    c1.info(f"Atual: {id_current['family']} / {id_current['model']}" if id_current else "Atual: modelo não identificado")
    c2.info(f"Proposto: {id_proposed['family']} / {id_proposed['model']}" if id_proposed else "Proposto: modelo não identificado")

if st.button("Analisar e decodificar", type="primary", use_container_width=True):
    if not current or not proposed:
        st.error("Preencha o código atual e o código proposto.")
        st.stop()
    id_current, id_proposed = identify(current), identify(proposed)
    if not id_current or not id_proposed:
        st.error("Um dos códigos não corresponde a nenhum modelo cadastrado.")
        st.stop()
    if id_current["family"] != id_proposed["family"]:
        st.error(f"Famílias diferentes: {id_current['family']} e {id_proposed['family']}. A comparação foi bloqueada.")
        st.stop()

    family = id_current["family"]
    min_len = RULES[family]["minimum_length"]
    if len(current) < min_len or len(proposed) < min_len:
        st.error(f"Para {family}, os códigos precisam ter pelo menos {min_len} caracteres.")
        st.stop()

    st.success(f"Família identificada: {family}")
    doc, pdf_path, status = pdf_status(family)
    (st.success if pdf_path and pdf_path.exists() else st.warning)(status)

    wt_rows, wt_violations = analyze(current, proposed, family)
    current_decoded, current_unknown = decode_code(current, family)
    proposed_decoded, proposed_unknown = decode_code(proposed, family)
    current_alerts = validate_documented_configuration(current, family)
    proposed_alerts = validate_documented_configuration(proposed, family)

    tab1, tab2, tab3 = st.tabs(["Comparação e WT", "Configuração atual", "Configuração proposta"])
    with tab1:
        df = pd.DataFrame(wt_rows)
        changed = df[df["Alterou?"] == "Sim"]
        review = changed[~changed["Resultado"].isin(["Solicitar WT", "Não solicitar WT"])]
        no_wt = changed[changed["Resultado"] == "Não solicitar WT"]
        k1, k2, k3 = st.columns(3)
        k1.metric("Campos alterados", len(changed))
        k2.metric("Alterações sem WT", len(no_wt))
        k3.metric("Pontos para análise", len(review) + len(wt_violations))
        st.dataframe(df, use_container_width=True, hide_index=True)
        for message in wt_violations:
            st.error(f"Regra especial violada: {message}")
    with tab2:
        st.dataframe(pd.DataFrame(current_decoded), use_container_width=True, hide_index=True)
        for message in current_alerts:
            st.error(message)
        for message in current_unknown:
            st.warning(f"Não documentado: {message}")
    with tab3:
        st.dataframe(pd.DataFrame(proposed_decoded), use_container_width=True, hide_index=True)
        for message in proposed_alerts:
            st.error(message)
        for message in proposed_unknown:
            st.warning(f"Não documentado: {message}")

with st.expander("Onde colocar os PDFs"):
    st.code("documentos/", language=None)
    st.write("Coloque cada PDF dentro da pasta `documentos`, usando exatamente o nome registrado no arquivo `regras_wt.json`.")

with st.expander("Famílias e modelos reconhecidos"):
    for family, cfg in RULES.items():
        st.markdown(f"**{family}:** {', '.join(cfg.get('model_prefixes', []))}")
