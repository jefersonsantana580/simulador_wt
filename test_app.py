from simulador_wt import identify, analyze

def test_mf7700():
    assert identify("7725KF0M0FB")["family"] == "MF 7700"
    rows, violations = analyze("7725KF0M0FB", "7725KF0K0ME", "MF 7700")
    assert next(r for r in rows if r["Posição"] == 8)["Resultado"] == "Verificar Tecnologia"
    assert not violations

def test_6700r():
    assert identify("6714RC49DMB")["family"] == "6700R"
