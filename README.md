# 🧬 Synapse Health | Challenge Oracle + FIAP 2026

Plataforma inteligente de gestão hospitalar, monitoramento epidemiológico preditivo e alocação dinâmica de recursos assistenciais, integrada nativamente ao **Oracle Cloud Autonomous Database** e potencializada por inteligência artificial generativa (**Oracle Select AI**).

---

## 📌 Sobre o Projeto
O **Synapse Health** foi desenvolvido como solução para o Challenge Oracle + FIAP. O sistema cruza dados públicos de saúde (DATASUS/SIH) com malhas geográficas e estatísticas (IBGE) e dados de infraestrutura (CNES), estruturando um pipeline completo de engenharia de dados, modelagem analítica e inteligência artificial para auxiliar gestores públicos e equipes hospitalares na tomada de decisão em tempo real.

---

## 🏗️ Arquitetura da Solução
A solução está estruturada em um pipeline ponta a ponta robusto e escalável na nuvem:
1. **Fontes de Dados:** Coleta de dados públicos de saúde e epidemiologia (**DATASUS**), malha territorial (**IBGE**) e capacidade instalada hospitalar (**CNES**).
2. **Preparação e Desenvolvimento:** Scripts em **Python** utilizando **Pandas** e **Google Colab** para limpeza, engenharia de atributos e transformações.
3. **Armazenamento:** Persistência relacional centralizada no **Oracle Cloud Autonomous Database**, estruturada com chaves primárias, estrangeiras e views analíticas.
4. **Processamento e Modelagem:** Consultas SQL avançadas no **Oracle SQL Developer** e algoritmos lógicos em Python para cálculo de prontidão e fadiga de equipes.
5. **Consumo e Visualização:** Portal interativo desenvolvido em **Streamlit**, oferecendo dashboards analíticos, mapas de calor e controle operacional.
6. **Inteligência Artificial:** Integração com o ecossistema nativo da Oracle via **Select AI (Modelo Cohere)** para conversão de linguagem natural em insights analíticos (*NL-to-SQL / Narrate*).

---

## 🛠️ Tecnologias e Bibliotecas Utilizadas
* **Linguagem:** Python 3.13
* **Banco de Dados & Nuvem:** Oracle Cloud Infrastructure (OCI), Oracle Autonomous Database, Oracle SQL Developer, oracledb (Oracle Wallet)
* **Engenharia e Análise de Dados:** Pandas, NumPy, PySUS
* **Visualização e Web App:** Streamlit, Plotly Express
* **Inteligência Artificial:** Oracle Select AI (Cohere Engine)

---

## 📂 Estrutura do Repositório
```text
├── 1_resumo_sazonalidade_sp.csv          # Indicadores sazonais consolidados do DATASUS
├── 2_internacoes_municipios_sp.csv       # Resumo geográfico e coordenadas por município
├── 3_top_diagnosticos_estacoes_sp.csv    # Ranking dos principais CIDs e patologias por estação
├── 4_leitos_cnes_municipios.csv          # Capacidade instalada de leitos (modelo CNES)
├── 5_prontidao_equipe.csv                # Matriz de prontidão, jornadas e índice de fadiga
├── 6_pareamento_escala_leitos.csv        # Escala operacional e pareamento entre leitos e equipes
├── app.py                                # Script principal da aplicação web em Streamlit
├── requirements.txt                      # Dependências e bibliotecas do projeto
└── README.md                             # Documentação técnica oficial do repositório
