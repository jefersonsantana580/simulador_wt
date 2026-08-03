import json
from pathlib import Path
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Simulador WT Tratores", page_icon="🚜", layout="wide")

@st.cache_data
def load_rules():
    path = Path(__file__).with_name("regras_wt.json")
    return json.loads(path.read_text(encoding="utf-8"))

RULES = load_rules()

def clean_code(value: str) -> str:
    return "".join(str(value or "").upper().split())

def identify(code: str):
    code = clean_code(code)
    candidates = []
    for family, cfg in RULES.items():
        for prefix in cfg["model_prefixes"]:
            if code.startswith(prefix):
                candidates.append((len(prefix), family, prefix))
    if not candidates:
        return None
    _, family, prefix = max(candidates, key=lambda x: x[0])
    return {"family": family, "model": prefix}

def char_at(code: str, position: int) -> str:
    return code[position - 1] if len(code) >= position else ""

def analyze(current: str, proposed: str, family: str):
    cfg = RULES[family]
    rows = []
    for field in cfg["fields"]:
        pos = field["position"]
        old = char_at(current, pos) if pos > 1 else current[:pos]
        new = char_at(proposed, pos) if pos > 1 else proposed[:pos]
        same = old == new
        action = field["action_if_equal"] if same else field["action_if_different"]
        rows.append({
            "Posição": pos,
            "Componente": field["label"],
            "Atual": old,
            "Proposto": new,
            "Alterou?": "Não" if same else "Sim",
            "Resultado": action,
        })

    violations = []
    for rule in cfg.get("special_rules", []):
        pos = rule["position"]
        if char_at(current, pos) == rule["when_current"] and char_at(proposed, pos) != rule["required_proposed"]:
            violations.append(rule["message"])
    return rows, violations

st.title("🚜 Simulador para WT de Tratores")
st.caption("Identificação automática da família e comparação do código atual com o código proposto.")

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

if st.button("Analisar códigos", type="primary", use_container_width=True):
    if not current or not proposed:
        st.error("Preencha o código atual e o código proposto.")
        st.stop()

    id_current = identify(current)
    id_proposed = identify(proposed)
    if not id_current:
        st.error("O código atual não corresponde a nenhum modelo cadastrado nas regras.")
        st.stop()
    if not id_proposed:
        st.error("O código proposto não corresponde a nenhum modelo cadastrado nas regras.")
        st.stop()
    if id_current["family"] != id_proposed["family"]:
        st.error(
            f"Os códigos pertencem a famílias diferentes: {id_current['family']} e {id_proposed['family']}. "
            "A comparação foi bloqueada porque as posições têm significados diferentes."
        )
        st.stop()

    family = id_current["family"]
    min_len = RULES[family]["minimum_length"]
    if len(current) < min_len or len(proposed) < min_len:
        st.error(f"Para {family}, os dois códigos precisam ter pelo menos {min_len} caracteres.")
        st.stop()

    rows, violations = analyze(current, proposed, family)
    df = pd.DataFrame(rows)

    st.success(f"Família identificada: {family}")
    if violations:
        for item in violations:
            st.error(f"Regra especial violada: {item}")

    changed = df[df["Alterou?"] == "Sim"]
    review_actions = changed[~changed["Resultado"].isin(["Solicitar WT", "Não solicitar WT"])]
    no_wt = changed[changed["Resultado"] == "Não solicitar WT"]

    k1, k2, k3 = st.columns(3)
    k1.metric("Campos alterados", len(changed))
    k2.metric("Alterações sem WT", len(no_wt))
    k3.metric("Pontos para análise", len(review_actions) + len(violations))

    def color_result(value):
        if value == "Não solicitar WT": return "background-color: #ff4b4b; color: white"
        if value == "Solicitar WT": return "background-color: #fff59d; color: black"
        return "background-color: #ffcc80; color: black"

    st.subheader("Resultado por posição")
    st.dataframe(df.style.map(color_result, subset=["Resultado"]), use_container_width=True, hide_index=True)

    st.subheader("Conclusão")
    if violations:
        st.error("Código proposto inválido por regra especial. Corrija antes de continuar.")
    elif len(review_actions):
        st.warning("Existem alterações que exigem avaliação especializada antes da decisão final.")
    elif len(no_wt):
        st.info("Há alterações classificadas como 'Não solicitar WT'. Consulte o detalhamento acima.")
    else:
        st.success("Todas as posições foram classificadas como 'Solicitar WT'.")

with st.expander("Famílias e modelos reconhecidos"):
    for family, cfg in RULES.items():
        st.markdown(f"**{family}:** {', '.join(cfg['model_prefixes'])}")
