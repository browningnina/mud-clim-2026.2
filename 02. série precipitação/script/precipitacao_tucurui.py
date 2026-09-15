# Marina Browning - 120056058

# Estação 1: Tucuruí 349000 (10/1970 a 07/2015)
# Estação 2: Goianésia 349002 (03/1985 a 01/2026)
# Localizadas no município de Tucuruí do Pará, Brasil.
# Fonte: Hidroweb - ANA (Agência Nacional de Águas e Saneamento Básico)

#%%
# importações
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# path 
path_tucurui = r"C:\Users\marin\Projetos\mud-clim-2026.2\02. série precipitação\excel\349000_Chuvas.csv"
path_goianesia = r"C:\Users\marin\Projetos\mud-clim-2026.2\02. série precipitação\excel\349002_Chuvas.csv"

#%%
from tabulate import tabulate
# Leitura
# a coluna "TotalAnual" teve que ser removida pois ela começa a ser preenchida a partir da linha 368, o que estava gerando erro na leitrua do csv
def carregar_dados(path):
    df = pd.read_csv(
        path,
        encoding="ISO-8859-1",
        decimal=",",
        sep=";",
        index_col="Data",
        header=10,
        usecols=lambda col: col != "TotalAnual"
    )
    
    return df

df_tucurui = carregar_dados(path_tucurui)
df_goianesia = carregar_dados(path_goianesia)

print(df_tucurui.columns.tolist())
print(tabulate(df_tucurui.head(), headers='keys', tablefmt='psql'))
print(df_goianesia.columns.tolist())
print(tabulate(df_goianesia.head(), headers='keys', tablefmt='psql'))
#%% TRATAMENTO DADOS 
''' priorizar consistencia 2, mas na falta de dados utilizar == 1
'''

def filtrar_consistencia(df):
    print("Nível de consistência:")
    print(df["NivelConsistencia"].value_counts(dropna=False).sort_index())

    # Define a prioridade: 2 > 1
    prioridade = {
        2: 0,
        1: 1
    }

    df = df.copy()
    df["_prioridade"] = df["NivelConsistencia"].map(prioridade)

    # Ordena por data e depois pela prioridade
    df = df.sort_values(["_prioridade"])

    # Para cada data, mantém a melhor consistência disponível
    df_filtrado = df[~df.index.duplicated(keep="first")].copy()

    # Remove coluna auxiliar
    df_filtrado = df_filtrado.drop(columns="_prioridade")

    print(f"\nTotal de registros antes do filtro: {len(df)}")
    print(f"Total de registros após o filtro: {len(df_filtrado)}")

    print("\nNível de consistência utilizado:")
    print(
        df_filtrado["NivelConsistencia"]
        .value_counts(dropna=False)
        .sort_index()
    )

    return df_filtrado

df_consistente1 = filtrar_consistencia(df_tucurui)
df_consistente2 = filtrar_consistencia(df_goianesia)
#%%
# Converter o índice para datetime
def preparar_datas(df):
    df = df.copy()

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

    return df
df_consistente1 = preparar_datas(df_consistente1)
df_consistente2 = preparar_datas(df_consistente2)
#%%
# AVALIAR DUPLICATAS

def avaliar_duplicadas(df):
    print(f"Linhas: {len(df)}")
    print(f"Datas únicas: {df.index.nunique()}")

    n_duplicadas = df.index.duplicated().sum()
    print(f"Datas duplicadas: {n_duplicadas}")

    duplicadas = df.index.duplicated(keep=False)

    if duplicadas.sum() > 0:
        df_duplicadas = (
            df.loc[
                duplicadas,
                [
                    "EstacaoCodigo",
                    "NivelConsistencia",
                    "TipoMedicaoChuvas",
                    "Total"
                ]
            ]
            .sort_index()
        )

        print("\nRegistros duplicados:")
        print(df_duplicadas)

        return df_duplicadas

    print("\nNão foram encontradas datas duplicadas.")

    return pd.DataFrame()

duplicadas_tucurui = avaliar_duplicadas(df_consistente1)
duplicadas_goianesia = avaliar_duplicadas(df_consistente2)
#%%
# identificando as colunas de chuva diaria 
import re

def identificar_colunas_chuva(df):
    colunas_chuva = [
        col for col in df.columns
        if re.fullmatch(r"Chuva\d{2}", str(col))
    ]
    
    print(f"Colunas de chuva encontradas: {len(colunas_chuva)}")
    print(colunas_chuva)
    
    return colunas_chuva
colunas_chuva1 = identificar_colunas_chuva(df_consistente1)
colunas_chuva2 = identificar_colunas_chuva(df_consistente2)
#%%
#série diária de precipitação
import pandas as pd
import numpy as np

def transformar_para_diaria(df, colunas_chuva):
    registros = []

    for data, linha in df.iterrows():
        ano = data.year
        mes = data.month

        for coluna in colunas_chuva:
            dia = int(coluna[-2:])

            # Verifica se o dia existe naquele mês
            try:
                data_diaria = pd.Timestamp(ano, mes, dia)
            except ValueError:
                continue

            valor = linha[coluna]
            consistencia = linha["NivelConsistencia"]

            registros.append({
                "Data": data_diaria,
                "precipitacao": valor,
                "NivelConsistencia": consistencia
            })

    serie = pd.DataFrame(registros)

    serie["precipitacao"] = pd.to_numeric(
        serie["precipitacao"],
        errors="coerce"
    )

    serie["NivelConsistencia"] = pd.to_numeric(
        serie["NivelConsistencia"],
        errors="coerce"
    )

    serie = serie.set_index("Data").sort_index()

    return serie

serie_tucurui = transformar_para_diaria(
    df_consistente1,
    colunas_chuva1
)

serie_goianesia = transformar_para_diaria(
    df_consistente2,
    colunas_chuva2
)
#%%
# comparação inicial das séries de Tucuruí e Goianésia

#encontrar periodo comum entre as duas séries
inicio_comum = max(
    serie_tucurui.index.min(),
    serie_goianesia.index.min()
)

fim_comum = min(
    serie_tucurui.index.max(),
    serie_goianesia.index.max()
)

print("Período comum:")
print(inicio_comum)
print(fim_comum)
tucurui_comum = serie_tucurui.loc[inicio_comum:fim_comum]
goianesia_comum = serie_goianesia.loc[inicio_comum:fim_comum]
#%% plot inicial serie diaria 
import matplotlib.pyplot as plt

plt.figure(figsize=(14, 6))

plt.plot(
    tucurui_comum.index,
    tucurui_comum["precipitacao"],
    label="Tucuruí",
    linewidth=0.8
)

plt.plot(
    goianesia_comum.index,
    goianesia_comum["precipitacao"],
    label="Goianésia",
    linewidth=0.8
)

plt.xlabel("Data")
plt.ylabel("Precipitação diária (mm)")
plt.title("Precipitação diária – período comum")
plt.legend()
plt.grid(alpha=0.3)

plt.tight_layout()
plt.show()
#%%
#comparar serie mensal com IC de 95%
dados_comuns = pd.DataFrame({
    "Tucurui": tucurui_comum["precipitacao"],
    "Goianesia": goianesia_comum["precipitacao"]
})

mensal = dados_comuns.resample("MS").mean()

def calcular_ic95(serie):
    media = serie.resample("MS").mean()
    desvio = serie.resample("MS").std()
    n = serie.resample("MS").count()

    erro = 1.96 * desvio / np.sqrt(n)

    limite_inferior = media - erro
    limite_superior = media + erro

    return media, limite_inferior, limite_superior

media_tucurui, inferior_tucurui, superior_tucurui = calcular_ic95(
    tucurui_comum["precipitacao"]
)

media_goianesia, inferior_goianesia, superior_goianesia = calcular_ic95(
    goianesia_comum["precipitacao"]
)

plt.figure(figsize=(14, 6))

plt.plot(
    media_tucurui.index,
    media_tucurui,
    label="Tucuruí"
)

plt.fill_between(
    media_tucurui.index,
    inferior_tucurui,
    superior_tucurui,
    alpha=0.2
)

plt.plot(
    media_goianesia.index,
    media_goianesia,
    label="Goianésia"
)

plt.fill_between(
    media_goianesia.index,
    inferior_goianesia,
    superior_goianesia,
    alpha=0.2
)

plt.xlabel("Data")
plt.ylabel("Precipitação média (mm)")
plt.title("Precipitação média mensal e IC 95% – período comum")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()
plt.show()
# %% BOXPLOT COMPARATIVO
import seaborn as sns

dados_boxplot = pd.DataFrame({
    "Tucuruí": tucurui_comum["precipitacao"],
    "Goianésia": goianesia_comum["precipitacao"]
})

dados_boxplot["Mes"] = dados_boxplot.index.month

dados_longos = dados_boxplot.reset_index().melt(
    id_vars=["Data", "Mes"],
    value_vars=["Tucuruí", "Goianésia"],
    var_name="Estacao",
    value_name="Precipitacao"
)
plt.figure(figsize=(14, 6))

sns.boxplot(
    data=dados_longos,
    x="Mes",
    y="Precipitacao",
    hue="Estacao"
)

plt.xlabel("Mês")
plt.ylabel("Precipitação diária (mm)")
plt.title("Distribuição da precipitação diária por mês – período comum")
plt.xticks(
    range(12),
    ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
     "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
)

plt.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.show()
''' tucurui apresneta precipitação mais alta e maior variabilidade, especialmente nos meses de janeiro a março. 
Goianésia apresenta precipitação mais baixa e menos extremos.'''
#%%
# MERGE DAS ESTAÇÕES
tucurui = serie_tucurui.rename(
    columns={
        "precipitacao": "prec_tucurui",
        "NivelConsistencia": "cons_tucurui"
    }
)

goianesia = serie_goianesia.rename(
    columns={
        "precipitacao": "prec_goianesia",
        "NivelConsistencia": "cons_goianesia"
    }
)

df_merge = tucurui.join(
    goianesia,
    how="outer"
).sort_index()

#%%
# PRIORIDADE REGRA

def selecionar_precipitacao(row):
    '''
Se apenas uma estação tiver dado naquela data → usa esse dado.
Se as duas tiverem dado:
se uma tem consistência 2 e outra 1 → usa a consistência 2;
se as duas têm consistência 2 → faz a média dos dois valores;
se as duas têm consistência 1 →  fazer a média das duas.'''

    tucurui = row["prec_tucurui"]
    goianesia = row["prec_goianesia"]

    cons_tucurui = row["cons_tucurui"]
    cons_goianesia = row["cons_goianesia"]

    # As duas possuem dados
    if pd.notna(tucurui) and pd.notna(goianesia):

        # As duas têm consistência 2
        if cons_tucurui == 2 and cons_goianesia == 2:
            return (tucurui + goianesia) / 2

        # Apenas Tucuruí tem consistência 2
        elif cons_tucurui == 2:
            return tucurui

        # Apenas Goianésia tem consistência 2
        elif cons_goianesia == 2:
            return goianesia

        # As duas têm consistência 1
        elif cons_tucurui == 1 and cons_goianesia == 1:
            return (tucurui + goianesia) / 2

    # Apenas Tucuruí possui dado
    elif pd.notna(tucurui):
        return tucurui

    # Apenas Goianésia possui dado
    elif pd.notna(goianesia):
        return goianesia

    return np.nan

df_merge["precipitacao"] = df_merge.apply(
    selecionar_precipitacao,
    axis=1
)
#%%
def identificar_fonte(row):

    tucurui = row["prec_tucurui"]
    goianesia = row["prec_goianesia"]

    cons_tucurui = row["cons_tucurui"]
    cons_goianesia = row["cons_goianesia"]

    if pd.notna(tucurui) and pd.notna(goianesia):

        if cons_tucurui == 2 and cons_goianesia == 2:
            return "Média T2 + G2"

        elif cons_tucurui == 2:
            return "Tucuruí C2"

        elif cons_goianesia == 2:
            return "Goianésia C2"

        else:
            return "Média T1 + G1"

    elif pd.notna(tucurui):
        return f"Tucuruí C{int(cons_tucurui)}"

    elif pd.notna(goianesia):
        return f"Goianésia C{int(cons_goianesia)}"

    return "Sem dados"

df_merge["fonte"] = df_merge.apply(
    identificar_fonte,
    axis=1
)
#%% SÉRIE FINAL
serie_final = df_merge[
    ["precipitacao", "fonte"]
].copy()
print(serie_final.index.min())
print(serie_final.index.max())

print(
    serie_final["fonte"]
    .value_counts()
)

#%%
# verificação final de lacunas na série 
# Random seed para garantir reprodutibilidade
rng = np.random.default_rng(42)

# Criar calendário diário completo
datas_completas = pd.date_range(
    start=serie_final.index.min(),
    end=serie_final.index.max(),
    freq="D"
)

# Inserir as datas ausentes
serie_imputada = serie_final.reindex(datas_completas)

serie_imputada.index.name = "Data"

# Identificar quais valores foram inseridos por imputação 
# 0 mm NÃO é considerado dado faltante
datas_imputadas = serie_imputada.index.difference(
    serie_final.index
)

print(f"Datas ausentes: {len(datas_imputadas)}")
#%%
# COMPLETAR DADOS FALTANTES
# Random seed para garantir reprodutibilidade
rng = np.random.default_rng(42)

def estimar_precipitacao(data, serie, rng, n_desvios=2):

    # Valores do mesmo dia e mês em outros anos
    candidatos = serie[
        (serie.index.month == data.month) &
        (serie.index.day == data.day) &
        (serie.index.year != data.year) &
        (serie.notna())
    ]

    if len(candidatos) == 0:
        return np.nan

    valores = candidatos.values.astype(float)

    # Média e desvio padrão
    media = np.mean(valores)
    desvio = np.std(valores, ddof=1)

    # Filtrar valores fora de ± 2 desvios padrão
    if desvio > 0:

        limite_inferior = media - n_desvios * desvio
        limite_superior = media + n_desvios * desvio

        valores_validos = valores[
            (valores >= limite_inferior) &
            (valores <= limite_superior)
        ]

    else:
        valores_validos = valores

    # Caso nenhum valor permaneça
    if len(valores_validos) == 0:
        valores_validos = valores

    # Média e desvio após filtragem
    media_final = np.mean(valores_validos)

    if len(valores_validos) > 1:
        desvio_final = np.std(
            valores_validos,
            ddof=1
        )
    else:
        desvio_final = 0

    # Sorteio considerando a variabilidade observada
    if desvio_final > 0:

        valor = rng.normal(
            loc=media_final,
            scale=desvio_final
        )

    else:

        valor = media_final

    # Precipitação não pode ser negativa
    valor = max(0, valor)

    return valor

for data in datas_imputadas:

    valor = estimar_precipitacao(
        data=data,
        serie=serie_final["precipitacao"],
        rng=rng,
        n_desvios=2
    )

    serie_imputada.loc[data, "precipitacao"] = valor
#%%
serie_imputada["tipo_dado"] = "observado"

serie_imputada.loc[
    datas_imputadas,
    "tipo_dado"
] = "imputado"
#%% Comparação da tendência em janelas móveis de 10 anos

serie_avaliacao = serie_final["precipitacao"].astype(float).sort_index()

# Total anual de precipitação
totais_anuais_tendencia = (
    serie_avaliacao
    .resample("YS")
    .sum(min_count=1)
    .dropna()
)

# Anos disponíveis
anos_disponiveis = totais_anuais_tendencia.index.year.to_numpy()

# Número de anos em cada janela
tamanho_janela = 10

# Último ano disponível
ultimo_ano = anos_disponiveis.max()

# Primeiro ano que permite formar uma janela completa de 10 anos
primeiro_ano = anos_disponiveis.min()

# Lista das janelas móveis
janelas = []

for ano_inicial in range(
    primeiro_ano,
    ultimo_ano - tamanho_janela + 2
):
    ano_final = ano_inicial + tamanho_janela - 1

    janelas.append(
        (
            f"{ano_inicial}-{ano_final}",
            ano_inicial,
            ano_final,
        )
    )


# Calculando a tendência de cada janela
resultados_tendencia = []

for nome_janela, ano_inicial, ano_final in janelas:

    dados_janela = totais_anuais_tendencia[
        (totais_anuais_tendencia.index.year >= ano_inicial)
        & (totais_anuais_tendencia.index.year <= ano_final)
    ]

    anos_janela = dados_janela.index.year.to_numpy()
    valores_janela = dados_janela.to_numpy()

    # Só calcula se houver exatamente 10 anos disponíveis
    if len(dados_janela) == tamanho_janela:

        coeficiente = np.polyfit(
            anos_janela,
            valores_janela,
            1
        )

        tendencia = np.polyval(
            coeficiente,
            anos_janela
        )

        resultados_tendencia.append(
            {
                "janela": nome_janela,
                "ano_inicial": ano_inicial,
                "ano_final": ano_final,
                "tendencia_mm_por_ano": coeficiente[0],
            }
        )

# Transformando os resultados em DataFrame
resultados_tendencia = pd.DataFrame(resultados_tendencia)

print("\nTendência em janelas móveis de 10 anos:")
print(resultados_tendencia)

#%% Gráfico das tendências
fig, eixo = plt.subplots(figsize=(15, 7))

eixo.plot(
    resultados_tendencia["ano_inicial"],
    resultados_tendencia["tendencia_mm_por_ano"],
    marker="o",
    linewidth=1,
)

eixo.axhline(
    0,
    linestyle="--",
    linewidth=1,
)

eixo.set_xlabel("Ano inicial da janela")
eixo.set_ylabel("Tendência (mm/ano)")
eixo.set_title(
    "Tendência da precipitação em janelas móveis de 10 anos"
)

eixo.grid(alpha=0.3)
plt.tight_layout()
plt.show()

''' Tendência negativa desde 2005, porém considerando as janelas móveis de 10 anos, a tendência geral apresenta certo crescimento desde 2010.'''
#%% Avaliação de variabilidade, valores extremos e mudanças aparentes
serie_avaliacao = serie_final["precipitacao"].astype(float).sort_index()

# Variabilidade: desvio-padrão e coeficiente de variação por ano.
avaliacao_anual = serie_avaliacao.resample("YS").agg(
    total="sum",
    media="mean",
    mediana="median",
    desvio_padrao="std",
    dias_chuvosos=lambda valores: (valores > 0).sum(),
)
avaliacao_anual["coeficiente_variacao"] = (
    avaliacao_anual["desvio_padrao"] / avaliacao_anual["media"].replace(0, np.nan)
)
print("\nVariabilidade anual:")
print(avaliacao_anual)

# Extremos pelo percentil 99 e pelo limite superior do IQR.
q1 = serie_avaliacao.quantile(0.25)
q3 = serie_avaliacao.quantile(0.75)
iqr = q3 - q1
limite_extremo = q3 + 1.5 * iqr
percentil_99 = serie_avaliacao.quantile(0.99)
extremos = serie_avaliacao[
    serie_avaliacao >= max(limite_extremo, percentil_99)
].sort_values(ascending=False)

print("\nLimites para valores extremos:")
print(f"Q1: {q1:.2f} mm | Q3: {q3:.2f} mm | IQR: {iqr:.2f} mm")
print(f"Limite superior do IQR: {limite_extremo:.2f} mm")
print(f"Percentil 99: {percentil_99:.2f} mm")
print("\nMaiores eventos de precipitação:")
print(extremos.head(20))

# Mudanças aparentes: médias móveis e tendência linear anual.
media_movel_90 = serie_avaliacao.rolling("90D", min_periods=30).mean()
totais_mensais = serie_avaliacao.resample("MS").sum(min_count=1)

anos = avaliacao_anual.index.year.to_numpy()
totais = avaliacao_anual["total"].to_numpy()
validos = ~np.isnan(totais)
coeficiente_tendencia = np.polyfit(anos[validos], totais[validos], 1)[0]
print(
    "\nMudança aparente no total anual: "
    f"{coeficiente_tendencia:.2f} mm/ano"
)
print("\nMédia móvel anual (12 meses):")

fig, eixos = plt.subplots(2, 1, figsize=(15, 9), sharex=False)
eixos[0].plot(
    avaliacao_anual.index,
    avaliacao_anual["total"],
    marker="o",
    linewidth=1,
    label="Precipitação anual",
)
eixos[0].plot(
    avaliacao_anual.index,
    np.polyval(np.polyfit(anos[validos], totais[validos], 1), anos),
    linestyle="--",
    label="Tendência linear aparente",
)

eixos[0].set_ylabel("Precipitação anual (mm)")
eixos[0].set_title("Mudanças aparentes no total anual")
eixos[0].grid(alpha=0.3)
eixos[0].legend()

eixos[1].plot(
    serie_avaliacao.index,
    media_movel_90,
    linewidth=0.8,
    label="Média móvel de 90 dias",
)
eixos[1].scatter(
    extremos.index,
    extremos.values,
    color="tab:red",
    s=12,
    label="Valores extremos",
)

print("\nComparação das tendências por janela temporal:")
eixos[1].set_xlabel("Data")
eixos[1].set_ylabel("Precipitação média (mm)")
eixos[1].set_title("Variabilidade e extremos ao longo do tempo")
eixos[1].grid(alpha=0.3)
eixos[1].legend()
plt.tight_layout()
plt.show()

#%% Decomposição sazonal em ciclos de 12 meses
from statsmodels.tsa.seasonal import seasonal_decompose

from statsmodels.tsa.seasonal import seasonal_decompose
import matplotlib.pyplot as plt

# Série mensal da precipitação consolidada
serie_mensal = (
    serie_final["precipitacao"]
    .resample("MS")
    .sum(min_count=1)
    .dropna()
)

# Decomposição sazonal
decomposicao = seasonal_decompose(
    serie_mensal,
    model="additive",
    period=12,
    extrapolate_trend="freq"
)

# Componente sazonal média por mês
sazonalidade_mensal = (
    decomposicao.seasonal
    .groupby(decomposicao.seasonal.index.month)
    .mean()
)

nomes_meses = [
    "Jan", "Fev", "Mar", "Abr", "Mai", "Jun",
    "Jul", "Ago", "Set", "Out", "Nov", "Dez"
]

sazonalidade_mensal.index = nomes_meses

print("\nComponente sazonal média por mês:")
print(sazonalidade_mensal.round(2))

# Gráfico da decomposição
fig, eixos = plt.subplots(
    4, 1,
    figsize=(15, 11),
    sharex=True
)

eixos[0].plot(
    serie_mensal,
    color="0.35"
)
eixos[0].set_title(
    "Série mensal de precipitação — série consolidada"
)

eixos[1].plot(
    decomposicao.trend,
    color="tab:blue"
)
eixos[1].set_title("Tendência")

eixos[2].plot(
    decomposicao.seasonal,
    color="tab:green"
)
eixos[2].set_title(
    "Sazonalidade — ciclo de 12 meses"
)

eixos[3].plot(
    decomposicao.resid,
    color="tab:red"
)
eixos[3].set_title("Resíduo")

for eixo in eixos:
    eixo.grid(alpha=0.3)
    eixo.set_ylabel("mm")

eixos[-1].set_xlabel("Data")

plt.tight_layout()
plt.show()
''' Resíduo aumentou muito a partir de 2018, mostrando que há padrões na série que não conseguem ser explicados pelos componentes de tendência e sazonalidade.'''
# %%
#variabilidade vs tendencia 

# Estatísticas móveis de 10 anos
janela = 120  # 120 meses = 10 anos

media_movel = serie_mensal.rolling(
    janela,
    min_periods=60
).mean()

desvio_movel = serie_mensal.rolling(
    janela,
    min_periods=60
).std()

cv_movel = (
    desvio_movel / media_movel
) * 100

fig, eixos = plt.subplots(
    2, 1,
    figsize=(15, 9),
    sharex=True
)

# Tendência / média móvel
eixos[0].plot(
    media_movel,
    color="tab:blue"
)

eixos[0].set_title(
    "Precipitação média — janela móvel de 10 anos"
)

eixos[0].set_ylabel("mm/mês")
eixos[0].grid(alpha=0.3)


# Variabilidade relativa
eixos[1].plot(
    cv_movel,
    color="tab:purple"
)

eixos[1].set_title(
    "Variabilidade relativa — coeficiente de variação"
)

eixos[1].set_ylabel("CV (%)")
eixos[1].set_xlabel("Data")
eixos[1].grid(alpha=0.3)

plt.tight_layout()
plt.show()
#%% Exportação da série preenchida
caminho_saida = (
    r"C:\Users\marin\Projetos\mud-clim-2026.2"
    r"\02. série precipitação\excel\Chuvas_preenchida.csv"
)
serie_final.to_csv(
    caminho_saida,
    sep=";",
    decimal=",",
    encoding="utf-8-sig",
    index_label="Data",
)
print(f"\nSérie preenchida exportada para: {caminho_saida}")