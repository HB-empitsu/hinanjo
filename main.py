import re
import unicodedata
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pyproj import Geod
from streamlit_folium import st_folium

import folium
import folium.plugins
import streamlit as st


def fetch_soup(url, parser="html5lib"):
    r = requests.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.content, parser)

    return soup


def fetch_hinanjo(url):
    soup = fetch_soup(url)

    tag = soup.find(string=re.compile(r"^補足情報"))
    information = (
        unicodedata.normalize("NFKC", tag.parent.get_text(strip=True)).replace("。", "。  \n").strip() if tag else ""
    )

    data = []

    for tr in soup.select("table.listViewTable > tbody > tr"):
        tds = tr.select("td")

        if len(tds) == 8:
            td = [i.get_text(strip=True) for i in tds]

            link = tds[3].select_one("a")

            text = link.get("onclick") or link.get("href")

            pattern = r"lat=([0-9.]+)&lng=([0-9.]+)"
            match = re.search(pattern, text)

            if match:
                lat = match.group(1)
                lng = match.group(2)

                td.append(lat)
                td.append(lng)
            else:
                print("No match found")

            data.append(td)

    if data:
        df = pd.DataFrame(
            data,
            columns=[
                "避難所名",
                "開設状況",
                "所在地",
                "地図",
                "電話番号",
                "収容人数",
                "避難世帯数",
                "避難人数",
                "緯度",
                "経度",
            ],
        )

        df = df.drop("地図", axis=1).astype({"収容人数": int, "緯度": float, "経度": float})

        df["避難世帯数"] = pd.to_numeric(df["避難世帯数"], errors="coerce").fillna(0).astype(int)
        df["避難人数"] = pd.to_numeric(df["避難人数"], errors="coerce").fillna(0).astype(int)

    else:
        df = pd.DataFrame(
            columns=[
                "避難所名",
                "開設状況",
                "所在地",
                "電話番号",
                "収容人数",
                "避難世帯数",
                "避難人数",
                "緯度",
                "経度",
            ]
        )

    return df, information


def set_color(value, max_value):
    if value == 0:
        return "blue"
    elif value <= max_value / 2:
        return "green"
    elif value <= max_value * 3 / 4:
        return "yellow"
    elif value <= max_value:
        return "red"
    else:
        return "black"


st.set_page_config(
    page_title="今治市 避難所情報", page_icon=None, layout="centered", initial_sidebar_state="auto", menu_items=None
)


@st.cache_data(ttl="1d")
def load_data():
    url = "https://city-imabari.my.salesforce-sites.com/K_PUB_VF_HinanjyoList"

    soup_list = fetch_soup(url)
    tag = soup_list.select_one("div.volunteer > dl")

    href = tag.select_one("a").get("href")
    link = urljoin(url, href)

    dt = tag.select_one("dt").get_text(strip=True)
    date, title = [i.get_text(strip=True) for i in tag.select("dd > p")]

    title = title.replace("今治市 避難所情報 :", "")

    status = "".join(dt.split())

    df, information = fetch_hinanjo(link)

    return df, title, status, date, link, information


df0, title, status, date, link, information = load_data()


st.title(title)

st.write("[避難所 詳細情報](%s)" % link)

st.subheader(f"{date} {status}")
st.write(f"{information}")

if not df0.empty:
    st.write(
        "開設数：", (df0["開設状況"] == "開設").sum(), "施設", "、閉鎖数：", (df0["開設状況"] == "閉鎖").sum(), "施設"
    )
    st.write("避難人数：", df0["避難人数"].sum(), "人、", "避難世帯数：", df0["避難世帯数"].sum(), "世帯")

    lat, lng = 34.0663183, 132.997528

    # フォリウムマップの初期化
    m = folium.Map(
        location=[lat, lng],
        tiles="https://cyberjapandata.gsi.go.jp/xyz/pale/{z}/{x}/{y}.png",
        attr='&copy; <a href="https://maps.gsi.go.jp/development/ichiran.html">国土地理院</a>',
        zoom_start=14,
    )

    df0["navi"] = df0.apply(
        lambda x: f'https://www.google.com/maps/dir/?api=1&destination={x["緯度"]},{x["経度"]}', axis=1
    )

    # データフレームからマーカーを追加
    for _, row in df0.iterrows():
        color = set_color(row["避難人数"], row["収容人数"])

        if row["開設状況"] != "開設":
            color = "gray"

        folium.Marker(
            location=[row["緯度"], row["経度"]],
            popup=folium.Popup(
                f'<p>{row["避難所名"]}<br>{row["収容人数"]}/{row["避難人数"]}/{row["避難世帯数"]}</p><p><a href="{row["navi"]}" target="_blank">ここへ行く</p>',
                max_width=300,
            ),
            tooltip=row["避難所名"],
            icon=folium.Icon(color=color),
        ).add_to(m)

    # 現在値
    folium.plugins.LocateControl().add_to(m)

    # マップをストリームリットに表示
    st_data = st_folium(m, width=500, height=300)

    # マップ境界内のデータフィルタリングと距離計算
    if st_data:
        bounds = st_data["bounds"]
        center = st_data.get("center", {"lat": lat, "lng": lng})

        southWest_lat = bounds["_southWest"]["lat"]
        southWest_lng = bounds["_southWest"]["lng"]
        northEast_lat = bounds["_northEast"]["lat"]
        northEast_lng = bounds["_northEast"]["lng"]

        # 境界内のポイントをフィルタリング
        filtered_df = df0.loc[
            (df0["緯度"] >= southWest_lat)
            & (df0["緯度"] <= northEast_lat)
            & (df0["経度"] >= southWest_lng)
            & (df0["経度"] <= northEast_lng)
        ].copy()

        # 距離計算
        grs80 = Geod(ellps="GRS80")
        filtered_df["distance"] = filtered_df.apply(
            lambda row: grs80.inv(center["lng"], center["lat"], row["経度"], row["緯度"])[2], axis=1
        )

        # 距離でソート
        filtered_df.sort_values("distance", inplace=True)

        # 結果を表示
        df1 = (
            filtered_df[
                [
                    "避難所名",
                    "開設状況",
                    "収容人数",
                    "避難人数",
                    "避難世帯数",
                    "所在地",
                    "電話番号",
                ]
            ]
            .head(20)
            .reset_index(drop=True)
        )

        st.dataframe(
            df1,
            column_config={
                "distance": "直線距離",
            },
            hide_index=True,
        )
else:
    st.write("避難所なし")
