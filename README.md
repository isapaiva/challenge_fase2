# 🧬 Synapse Health | Challenge Oracle + FIAP 2026

Plataforma inteligente de gestão hospitalar, monitoramento epidemiológico preditivo e alocação dinâmica de recursos assistenciais, integrada nativamente ao **Oracle Cloud Autonomous Database** e potencializada por inteligência artificial generativa (**Oracle Select AI**).

---

## 📌 Sobre o Projeto
O **Synapse Health** foi desenvolvido para apoiar gestores do SUS e secretarias de saúde na tomada de decisões estratégicas e operacionais. O sistema cruza dados públicos de saúde (SIH/SUS, DATASUS) com malhas geográficas, demográficas (IBGE) e dados de infraestrutura hospitalar (CNES), estruturando um pipeline completo de engenharia de dados, modelagem analítica e inteligência artificial para auxiliar gestores públicos e equipes hospitalares na tomada de decisão em tempo real.

---

## 🏗️ Arquitetura da Solução
A solução está estruturada em um pipeline ponta a ponta robusto e escalável na nuvem:
1. **Fontes de Dados:** Coleta de dados públicos de saúde e indicadores operacionais (**DATASUS**), dados estatísticos e demográficos (**IBGE**) e cadastro de estabelecimentos (**CNES**).
2. **Preparação e Desenvolvimento:** Scripts em **Python** utilizando **Pandas**, **Google Colab**, **PyCharm** e estruturação de interfaces em **HTML/CSS Inline**.
3. **Armazenamento:** Persistência relacional centralizada no **Oracle Cloud Autonomous Database**, estruturada com chaves primárias, estrangeiras e views analíticas.
4. **Processamento e Modelagem:** Consultas SQL avançadas no **Oracle SQL Developer** e algoritmos lógicos em Python para cálculo de prontidão, agregação e indicadores estatísticos.
5. **Consumo e Visualização:** Portal interativo desenvolvido em **Streamlit** com **Plotly Express**, oferecendo dashboards analíticos, mapas e controle operacional.
6. **Inteligência Artificial:** Integração com o ecossistema nativo da Oracle via **Select AI (Modelo Cohere)** para conversão de linguagem natural em insights analíticos (*NL-to-SQL / Narrate*).

---

## 🛠️ Tecnologias e Bibliotecas Utilizadas
* **Linguagem:** Python 3.13
* **Banco de Dados & Nuvem:** Oracle Cloud Infrastructure (OCI), Oracle Autonomous Database, Oracle SQL Developer, oracledb (Oracle Wallet)
* **Engenharia e Análise de Dados:** Pandas, NumPy, PySUS
* **Visualização e Web App:** Streamlit, Plotly Express
* **Inteligência Artificial:** Oracle Select AI (Cohere Engine)
* **Gestão Ágil:** Trello

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
├── README.md                             # Documentação técnica oficial do repositório
└── sprint_2.ipynb                        # Notebook Google Colab com a extração e desenvolvimento dos dados
```

---

## 🚀 Como Executar o Projeto Localmente

Para clonar e rodar o projeto diretamente no seu ambiente de desenvolvimento, execute os comandos abaixo no seu terminal:

```bash
git clone [https://github.com/isapaiva/challenge_fase2.git](https://github.com/isapaiva/challenge_fase2.git)
cd CHALLENGE_FASE2
pip install -r requirements.txt
```

Para configurar as credenciais do Oracle Cloud (Streamlit Secrets), crie uma pasta `.streamlit` na raiz do projeto e um arquivo `secrets.toml` com as credenciais de acesso ao seu Autonomous Database e o caminho para o diretório da sua Oracle Wallet:

```toml
[oracle]
user = "seu_usuario"
password = "sua_senha"
dsn = "seu_conexao_high"
wallet_location = "caminho_para_sua_wallet"
```

Por fim, inicialize a aplicação com o Streamlit:

```bash
streamlit run ec_fiap_final.py
```

