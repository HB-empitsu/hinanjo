import math

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import streamlit as st

st.set_page_config(
    page_title="今治市 避難所情報", page_icon=None, layout="wide", initial_sidebar_state="auto", menu_items=None
)


@st.cache_data
def load_data():
    df_info = pd.read_csv("info.csv", index_col="date", parse_dates=True)
    df_data = pd.read_csv("data.csv", parse_dates=["日付"])

    return df_info, df_data


df_info, df_data = load_data()

df0 = df_data[df_data["避難人数"] > 0].copy()

pv = df0.pivot(index="日付", columns="避難所名", values="避難人数").reindex(index=df_info.index).fillna(0).astype(int)
df1 = pv.assign(合計=pv.sum(axis=1)).copy()

df2 = pv.diff().fillna(pv).astype(int).copy()
df2 = df2.assign(合計=df2.sum(axis=1))

st.title("2024年8月28日　台風10号災害")

tab1, tab2, tab3, tab4 = st.tabs(["利用避難所一覧", "利用避難所差分", "避難所別利用状況", "避難者利用状況"])

tab1.subheader("利用避難所一覧")
tab1.table(df1)

tab2.subheader("利用避難所差分")
tab2.table(df2)

tab3.subheader("避難所別利用状況")

rows = math.ceil(pv.shape[1] / 4)

# サブプロットの作成
fig1 = make_subplots(rows=rows, cols=4, shared_xaxes=True, shared_yaxes=True, subplot_titles=pv.columns)

# 各サブプロットにデータを追加
for i, col in enumerate(pv.columns):
    row = i // 4 + 1
    col_num = i % 4 + 1

    fig1.add_trace(
        go.Scatter(x=pv.index, y=pv[col], mode="lines", line_shape="hv", fill="tozeroy", name=col), row=row, col=col_num
    )

# レイアウトの更新
fig1.update_layout(height=800, showlegend=False)

# Y軸の範囲を統一
fig1.update_yaxes(range=[0, 15])

fig1.update_xaxes(
    showgrid=True,
    # showticklabels=True,
    gridwidth=1,
    gridcolor="LightGray",
    dtick=6 * 60 * 60 * 1000,  # 3時間
)


# グラフの表示
tab3.plotly_chart(fig1)

tab4.subheader("避難者利用状況")

# 積み上げグラフの作成
fig2 = go.Figure()

for column in pv.columns:
    fig2.add_trace(
        go.Scatter(
            x=pv.index,
            y=pv[column],
            mode="lines",
            name=column,
            stackgroup="one",
            line_shape="hv",
        )
    )

# グラフのレイアウト設定
fig2.update_layout(
    # title="避難所別の積み上げグラフ",
    xaxis_title="日付",
    yaxis_title="避難人数",
    hovermode="x unified",
    legend=dict(
        xanchor="left",
        yanchor="bottom",
        x=0.05,
        y=0.6,
        orientation="v",
    ),
    height=800,
)

fig2.update_xaxes(
    showgrid=True,
    gridwidth=1,
    gridcolor="LightGray",
    dtick=3 * 60 * 60 * 1000,  # 3時間
)

tab4.plotly_chart(fig2)
