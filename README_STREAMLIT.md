# Simulador WT Tratores

Aplicação Streamlit que identifica automaticamente a família do código atual e do código proposto, compara as posições relevantes e aplica as regras extraídas da planilha `Simulador para WT_Tratores.xlsx`.

## Arquivos

- `simulador_wt.py`: interface e motor de análise.
- `regras_wt.json`: regras por família, posições, componentes e ações.
- `requirements.txt`: dependências.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run simulador_wt.py
```

## Observações importantes

- A identificação usa o maior prefixo de modelo compatível.
- Códigos de famílias diferentes são bloqueados, pois a semântica das posições muda.
- As regras especiais descritas no rodapé das abas foram incorporadas.
- Antes de publicar em produção, valide os exemplos de todas as famílias com os responsáveis pelo processo.
