import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Simulador WT Tratores", page_icon="🚜", layout="wide")
BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = BASE_DIR / "documentos"

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

# Fallback documental da MF 7700. Mantém a decodificação funcionando mesmo se
# um regras_wt.json antigo for publicado por engano no repositório.
MF7700_DOCUMENTATION = {
    "title": "Série MF 7700 Dyna-6 - Lógicas dos Pacotes de Vendas",
    "pdf_file": "IP_Tratores Série MF 7700 Dyna-6 Lógicas dos Pacotes de Vendas.pdf",
    "position_values": {
        "6": {
            "1": "Pacote Standard 1",
            "2": "Pacote Standard 2",
            "F": "Pacote Efficient",
            "M": "Pacote Exclusive",
            "W": "Pacote Transbordo"
        },
        "7": {
            "E": "Rodagem: dianteiro 16.9-28 R1; traseiro 24.5-32 R1",
            "R": "Rodagem: dianteiro 16.9-28 R1; traseiro 30.5-32 R1",
            "Q": "Rodagem: dianteiro 600/65R28; traseiro 710/70R38",
            "N": "Rodagem: dianteiro 16.9-30 R1; traseiro 20.8-42 R1 duplo",
            "0": "Rodagem: dianteiro 600/65R28 R1; traseiro 520/85R42 R1 duplo",
            "3": "Rodagem: dianteiro 18.4-26 R2; traseiro 20.8-42 R2 duplo",
            "4": "Rodagem: dianteiro 420/90R30 R2; traseiro 520/85R42 R2 duplo"
        },
        "8": {
            "U": "Sem piloto automático + Massey Connect",
            "B": "Preparação para piloto automático",
            "M": "Piloto automático decimétrico Trimble + Massey Connect",
            "N": "Piloto automático centimétrico Trimble + rádio RTK Trimble + Massey Connect",
            "V": "Preparação para piloto automático + Massey Connect",
            "W": "Piloto automático centimétrico Trimble + rádio RTK Trimble + base RTK MR-2 + Massey Connect"
        },
        "9": {"0": "Sem acessórios"},
        "10": {
            "M": "Pneu Michelin",
            "G": "Pneu Standard, conforme disponibilidade",
            "F": "Pneu Standard, conforme disponibilidade",
            "P": "Pneu Standard, conforme disponibilidade"
        },
        "11": {"B": "Mercado Brasil", "E": "Mercado OSA"}
    },
    "restrictions": [
        {"position": 8, "value": "U", "required": {"position": 6, "value": "1"}, "message": "Tecnologia 'U' somente está documentada para o pacote Standard '1'."},
        {"position": 8, "value": "B", "required": {"position": 6, "value": "2"}, "message": "Tecnologia 'B' somente está documentada para o pacote Standard '2'."},
        {"position": 6, "values": ["1", "2"], "model_prefix": "7719", "message": "Pacote Standard está documentado apenas para o modelo MF 7719."}
    ]
}

if "MF 7700" in RULES:
    RULES["MF 7700"].setdefault("documentation", MF7700_DOCUMENTATION)

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
        return None, None, "Ainda não há mapa documental cadastrado para esta família no regras_wt.json."
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

if st.button("Analisar e decodificar", type="primary", use_container_width=True):
    if not current or not proposed:
        st.error("Preencha o código atual e o código proposto.")
        st.stop()

    id_current, id_proposed = identify(current), identify(proposed)
    if not id_current or not id_proposed:
        st.error("Um dos códigos não corresponde a nenhum modelo cadastrado.")
        st.stop()
    if id_current["family"] != id_proposed["family"]:
        st.error(
            f"Os códigos pertencem a famílias diferentes: {id_current['family']} e "
            f"{id_proposed['family']}. A comparação foi bloqueada."
        )
        st.stop()

    family = id_current["family"]
    min_len = RULES[family]["minimum_length"]
    if len(current) < min_len or len(proposed) < min_len:
        st.error(f"Para {family}, os códigos precisam ter pelo menos {min_len} caracteres.")
        st.stop()

    wt_rows, wt_violations = analyze(current, proposed, family)
    current_decoded, current_unknown = decode_code(current, family)
    proposed_decoded, proposed_unknown = decode_code(proposed, family)
    current_alerts = validate_documented_configuration(current, family)
    proposed_alerts = validate_documented_configuration(proposed, family)

    current_by_position = {row["Posição"]: row for row in current_decoded}
    proposed_by_position = {row["Posição"]: row for row in proposed_decoded}

    changes = []
    for row in wt_rows:
        if row["Alterou?"] != "Sim":
            continue
        position = row["Posição"]
        old_cfg = current_by_position.get(position, {}).get("Configuração", "Não documentado")
        new_cfg = proposed_by_position.get(position, {}).get("Configuração", "Não documentado")
        changes.append({
            "Posição": position,
            "Componente": row["Componente"],
            "De": f"{row['Atual']} | {old_cfg}",
            "Para": f"{row['Proposto']} | {new_cfg}",
            "Análise WT": row["Resultado"],
        })

    st.subheader("Resumo das alterações")
    st.caption(f"{family} | {current} → {proposed}")

    if changes:
        changes_df = pd.DataFrame(changes)
        st.dataframe(changes_df, use_container_width=True, hide_index=True)

        review_count = sum(
            item["Análise WT"] not in ["Solicitar WT", "Não solicitar WT"]
            for item in changes
        )
        no_wt_count = sum(item["Análise WT"] == "Não solicitar WT" for item in changes)

        c1, c2, c3 = st.columns(3)
        c1.metric("Alterações", len(changes))
        c2.metric("Sem necessidade de WT", no_wt_count)
        c3.metric("Exigem verificação", review_count + len(wt_violations))
    else:
        st.info("Nenhuma alteração foi identificada entre os códigos.")

    for message in wt_violations:
        st.error(f"Regra de WT: {message}")
    for message in current_alerts:
        st.warning(f"Código atual: {message}")
    for message in proposed_alerts:
        st.warning(f"Código proposto: {message}")

    # Mostra somente os valores não documentados que participam de uma alteração.
    changed_positions = {item["Posição"] for item in changes}
    for decoded_row in proposed_decoded:
        if (
            decoded_row["Posição"] in changed_positions
            and decoded_row["Configuração"] == "Valor não documentado no PDF cadastrado"
        ):
            st.warning(
                f"Valor proposto não documentado: posição {decoded_row['Posição']} "
                f"({decoded_row['Componente']}) = '{decoded_row['Código']}'."
            )

