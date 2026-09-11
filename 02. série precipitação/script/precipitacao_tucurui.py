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
    """Preenche somente a lacuna com bootstrap empírico sazonal mensal.

    Os valores sorteados vêm da distribuição observada do mesmo mês, usando
    apenas registros fora da lacuna. Assim, zeros, chuvas fracas e eventos
    intensos são preservados sem interpolação linear.
    """
    df_preenchido = df.copy()
    inicio = pd.Timestamp(inicio)
    fim = pd.Timestamp(fim)
    rng = np.random.default_rng(random_state)

    chuva = (
        df.loc[:, colunas]
        .replace(r"^\s*$", np.nan, regex=True)
        .replace(["n/a", "N/A", "NaN"], np.nan)
        .apply(pd.to_numeric, errors="coerce")
    )

    fora_lacuna = (df.index < inicio) | (df.index > fim)
    historico = {
        mes: chuva.loc[fora_lacuna & (df.index.month == mes), colunas]
        .stack()
        .dropna()
        .to_numpy()
        for mes in range(1, 13)
    }

    if any(valores.size == 0 for valores in historico.values()):
        meses_sem_historico = [
            str(mes) for mes, valores in historico.items() if valores.size == 0
        ]
        raise ValueError(
            "Não há observações para os meses: "
            + ", ".join(meses_sem_historico)
        )

    df_preenchido["DadoSintetico"] = False
    for posicao, indice in enumerate(df.index):
        if not inicio <= indice <= fim:
            continue

        dias_no_mes = indice.days_in_month
        mes = indice.month
        amostra = rng.choice(historico[mes], size=dias_no_mes, replace=True)

        for dia in range(1, dias_no_mes + 1):
            coluna = f"Chuva{dia:02d}"
            if coluna not in colunas:
                continue
            coluna_posicao = chuva.columns.get_loc(coluna)
            if pd.isna(chuva.iat[posicao, coluna_posicao]):
                chuva.iat[posicao, coluna_posicao] = max(
                    0.0, float(amostra[dia - 1])
                )
                df_preenchido.iloc[posicao, df_preenchido.columns.get_loc(
                    "DadoSintetico"
                )] = True

    df_preenchido.loc[:, colunas] = chuva
    return df_preenchido


df = preencher_chuva_na(df, colunas_chuva)
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

'''  foi avalaido que as duplicadas são referentes a mesma data 
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
