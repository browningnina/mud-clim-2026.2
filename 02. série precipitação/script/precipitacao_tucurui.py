# Marina Browning - 120056058

# Dados de precipitação da estação pluviométrica TUCURUÍ, localizada no estado do Pará, Brasil.
# Fonte: Hidroweb - ANA (Agência Nacional de Águas e Saneamento Básico)
# Código da Estação pluviométrica TUCURUÍ: 349000
# Coordenadas: lat -3.7603 lon -49.6667
# Período contemplado: 10/1995 a 07/2015

#%%
# importações
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# path 
path_precipitacao = r"C:\Users\marin\Projetos\mud-clim-2026.2\02. série precipitação\excel\349000_Chuvas.csv"
            
#%%
from tabulate import tabulate
# Leitura
# a coluna "TotalAnual" teve que ser removida pois ela começa a ser preenchida a partir da linha 368, o que estava gerando erro na leitrua do csv
df = pd.read_csv(
    path_precipitacao,
    encoding="ISO-8859-1",
    decimal = ",",
    sep=";",
    index_col="Data",
    header = 10,
    usecols=lambda col: col != "TotalAnual"
    )

print(df.columns.tolist())
print(tabulate(df.head(), headers='keys', tablefmt='psql'))
#%%
# Converter o índice para datetime
df.index = pd.to_datetime(
    df.index,
    format="%d/%m/%Y"
)

# Ordenar cronologicamente
df = df.sort_index()

# Criar ano e mês
df["Ano"] = df.index.year
df["Mes"] = df.index.month

#%%
# identificando as colunas de chuva diaria 
import re

colunas_chuva = [
    col for col in df.columns
    if re.fullmatch(r"Chuva\d{2}", str(col))
]
print(colunas_chuva)

def preencher_chuva_na(
    df,
    colunas,
    inicio="1996-07-01",
    fim="1999-02-01",
    random_state=42,
):
    """Preenche a lacuna no formato mensal original do HidroWeb.

    O valor de cada dia é sorteado, com reposição, da distribuição observada
    no mesmo mês em outros anos fora da lacuna. Isso preserva a sazonalidade,
    a frequência de dias secos e os eventos intensos sem interpolação linear.
    """
    inicio = pd.Timestamp(inicio)
    fim = pd.Timestamp(fim)
    if inicio.day != 1 or fim.day != 1 or inicio > fim:
        raise ValueError("inicio e fim devem ser o primeiro dia de um mês.")

    resultado = df.copy()
    resultado.index = pd.to_datetime(resultado.index)

    meses_lacuna = pd.date_range(inicio, fim, freq="MS")
    indice_original = resultado.index
    meses_novos = meses_lacuna[~meses_lacuna.isin(indice_original)]
    if len(meses_novos) > 0:
        novas_linhas = pd.DataFrame(
            index=meses_novos,
            columns=resultado.columns,
        )
        resultado = pd.concat([resultado, novas_linhas], axis=0)
    resultado = resultado.sort_index()
    resultado.index.name = df.index.name or "Data"

    valores = (
        df.loc[:, colunas]
        .replace(r"^\s*$", np.nan, regex=True)
        .replace(["n/a", "N/A", "NaN"], np.nan)
        .apply(pd.to_numeric, errors="coerce")
    )
    valores.index = indice_original
    # Duplicatas do HidroWeb são mantidas no resultado, mas uma única
    # observação por mês é usada para calcular a distribuição histórica.
    valores = valores.groupby(level=0).first()
    fora_lacuna = ~valores.index.isin(meses_lacuna)
    rng = np.random.default_rng(random_state)
    historico = {}

    for mes in range(1, 13):
        linhas_mes = valores.loc[fora_lacuna & (valores.index.month == mes)]
        historico[mes] = {
            coluna: linhas_mes[coluna].dropna().to_numpy()
            for coluna in colunas
        }
        if not any(amostras.size for amostras in historico[mes].values()):
            raise ValueError(f"Não há dados históricos para o mês {mes}.")

        historico[mes]["_mensal"] = (
            linhas_mes[colunas].stack().dropna().to_numpy()
        )

    resultado["DadoSintetico"] = False
    for data in meses_lacuna:
        dias_no_mes = data.days_in_month
        for dia in range(1, 32):
            coluna = f"Chuva{dia:02d}"
            if coluna not in colunas:
                continue

            if dia > dias_no_mes:
                resultado.at[data, coluna] = np.nan
                continue

            atual = resultado.at[data, coluna]
            vazio = pd.isna(atual) or str(atual).strip().lower() in {
                "n/a", "nan", ""
            }
            if not vazio:
                continue

            amostras = historico[data.month][coluna]
            if amostras.size == 0:
                amostras = historico[data.month]["_mensal"]
            resultado.at[data, coluna] = max(
                0.0, float(rng.choice(amostras))
            )
            resultado.at[data, "DadoSintetico"] = True

    if "Ano" in resultado.columns:
        resultado["Ano"] = resultado.index.year
    if "Mes" in resultado.columns:
        resultado["Mes"] = resultado.index.month
    return resultado


df = preencher_chuva_na(
    df,
    colunas_chuva,
    inicio="1996-07-01",
    fim="1999-02-01",
    random_state=42,
)
#%% avaliacao de duplicadas 
print("Linhas:", len(df))
print("Datas únicas:", df.index.nunique())
print("Datas duplicadas:", df.index.duplicated().sum())

duplicadas = df.index.duplicated(keep=False)

print(
    df.loc[duplicadas, 
           ["EstacaoCodigo", "NivelConsistencia", "TipoMedicaoChuvas", "Total"]]
    .sort_index()
)
#%%

'''  foi avaliado que as duplicadas são referentes a mesma data 
    mas com diferentes niveis de consistencia, 
    irei priorizar o tipo 1 que é o que mais tem dados
'''

def filtrar_consistencia_2(df):
    print("Nível de consistência:")
    print(df["NivelConsistencia"].value_counts().sort_index())

    df_filtrado = df[df["NivelConsistencia"] == 1].copy()

    print(f"\nTotal de registros antes do filtro: {len(df)}")
    print(f"Total de registros com consistência 1: {len(df_filtrado)}")

    return df_filtrado
df_consistente = filtrar_consistencia_2(df)
# %%
# Transformando a tabela mensal em série diária.
dias = np.array([int(coluna[-2:]) for coluna in colunas_chuva])
datas_mensais = np.repeat(df.index.to_numpy(), len(colunas_chuva))
datas_diarias = pd.to_datetime(
    {
        "year": pd.DatetimeIndex(datas_mensais).year,
        "month": pd.DatetimeIndex(datas_mensais).month,
        "day": np.tile(dias, len(df)),
    },
    errors="coerce",
)
serie_diaria = pd.DataFrame(
    {
        "precipitacao": pd.to_numeric(
            df[colunas_chuva].to_numpy().ravel(), errors="coerce"
        ),
        "sintetica": np.repeat(
            df["DadoSintetico"].to_numpy(), len(colunas_chuva)
        ),
    },
    index=datas_diarias,
).dropna(subset=["precipitacao"])
serie_diaria = serie_diaria.sort_index()

# Mantém apenas datas válidas e destaca a lacuna preenchida.
serie_diaria = serie_diaria.loc[serie_diaria.index.notna()]
periodo_sintetico = (
    (serie_diaria.index >= pd.Timestamp("1996-07-01"))
    & (serie_diaria.index <= pd.Timestamp("1999-02-28"))
    & serie_diaria["sintetica"]
)

plt.figure(figsize=(15, 5))
plt.plot(
    serie_diaria.index,
    serie_diaria["precipitacao"],
    color="0.65",
    linewidth=0.7,
    label="Dados observados",
)
plt.plot(
    serie_diaria.index[periodo_sintetico],
    serie_diaria.loc[periodo_sintetico, "precipitacao"],
    color="tab:orange",
    linewidth=0.8,
    label="Dados sintéticos",
)
plt.axvspan(
    pd.Timestamp("1996-07-01"),
    pd.Timestamp("1999-02-28"),
    color="tab:orange",
    alpha=0.12,
)
plt.xlabel("Data")
plt.ylabel("Precipitação (mm)")
plt.title("Série diária de precipitação — Estação TUCURUÍ")
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()
plt.show()
