import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# =========================================================
# 1. 기본 설정
# =========================================================

st.set_page_config(
    page_title="동네별 인구 피라미드",
    page_icon="🏘️",
    layout="wide"
)

st.markdown("""
<style>
    .stApp {
        background-color: #FFF9F2;
    }

    h1, h2, h3 {
        color: #70452F;
    }

    .intro {
        color: #795548;
        font-size: 17px;
        line-height: 1.7;
    }

    div[data-testid="stMetric"] {
        background-color: #FFFFFF;
        border: 1px solid #F0DCCB;
        padding: 16px;
        border-radius: 12px;
    }

    .insight-card {
        background-color: #FFFFFF;
        border: 1px solid #F0DCCB;
        border-radius: 12px;
        padding: 16px 20px;
        margin-top: 12px;
        margin-bottom: 12px;
        color: #70452F;
        font-size: 16px;
        line-height: 1.7;
    }

    .warning-text {
        color: #B54708;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)


# =========================================================
# 2. 데이터 불러오기
# =========================================================

DATA_URL = (
    "https://raw.githubusercontent.com/"
    "greatsong/modudata/main/data/population_yearly.csv.gz"
)


@st.cache_data
def load_data():
    df = pd.read_csv(DATA_URL, compression="gzip")
    df.columns = df.columns.astype(str).str.strip()

    df["연도"] = pd.to_numeric(df["연도"], errors="coerce")
    df = df.dropna(subset=["연도"]).copy()
    df["연도"] = df["연도"].astype(int)

    latest_year = df["연도"].max()
    df = df[df["연도"] == latest_year].copy()

    for col in ["시도", "시군구", "동"]:
        df[col] = df[col].astype("string").str.strip()

    return df, latest_year


st.title("🏘️ 동네별 인구 피라미드")

st.markdown(
    '<p class="intro">'
    '우리 동네에는 연령대별로 얼마나 많은 사람이 살고 있을까요? '
    '시도, 시군구, 동을 선택해 남녀 인구 구성과 주요 인구 지표를 살펴보세요.'
    '</p>',
    unsafe_allow_html=True
)

try:
    with st.spinner("인구 데이터를 불러오는 중입니다..."):
        df, latest_year = load_data()

except Exception as e:
    st.error("데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
    st.caption(f"오류 내용: {e}")
    st.stop()

if df.empty:
    st.warning("최신 연도에 해당하는 데이터가 없습니다.")
    st.stop()


# =========================================================
# 3. 지역 선택: 시도 → 시군구 → 동
# =========================================================

st.subheader("📍 우리 동네 선택")

col1, col2, col3 = st.columns(3)

with col1:
    sido_list = sorted(df["시도"].dropna().unique().tolist())

    if not sido_list:
        st.warning("선택할 시도 데이터가 없습니다.")
        st.stop()

    selected_sido = st.selectbox("① 시도", options=sido_list)

sido_df = df[df["시도"] == selected_sido].copy()

with col2:
    sigungu_list = sorted(
        sido_df["시군구"].dropna().unique().tolist()
    )

    if not sigungu_list:
        st.warning("선택한 시도에 시군구 데이터가 없습니다.")
        st.stop()

    selected_sigungu = st.selectbox(
        "② 시군구",
        options=sigungu_list
    )

sigungu_df = sido_df[
    sido_df["시군구"] == selected_sigungu
].copy()

with col3:
    dong_list = sorted(
        sigungu_df["동"].dropna().unique().tolist()
    )

    if not dong_list:
        st.warning("선택한 시군구에 동 데이터가 없습니다.")
        st.stop()

    selected_dong = st.selectbox("③ 동", options=dong_list)


# =========================================================
# 4. 선택한 동네의 인구 데이터 찾기
# =========================================================

selected_df = df[
    (df["시도"] == selected_sido)
    & (df["시군구"] == selected_sigungu)
    & (df["동"] == selected_dong)
].copy()

if selected_df.empty:
    st.warning("선택한 지역의 인구 자료가 없습니다.")
    st.stop()

if len(selected_df) > 1:
    st.warning(
        "같은 지역에 여러 행이 있습니다. "
        "데이터의 중복 여부를 확인해 주세요."
    )

# 중복 행이 있다면 첫 번째 행을 사용합니다.
row = selected_df.iloc[0]


# =========================================================
# 5. 나이별 남녀 인구 계산
# =========================================================

ages = list(range(101))

age_labels = [
    f"{age}세" for age in range(100)
] + ["100세 이상"]

male_columns = [
    f"남_{age}세" for age in range(100)
] + ["남_100세 이상"]

female_columns = [
    f"여_{age}세" for age in range(100)
] + ["여_100세 이상"]


def get_population(row, column):
    """인구 값을 안전하게 숫자로 변환합니다."""
    if column not in row.index:
        return 0

    value = pd.to_numeric(row[column], errors="coerce")

    if pd.isna(value):
        return 0

    return max(0, int(value))


male_population = [
    get_population(row, col)
    for col in male_columns
]

female_population = [
    get_population(row, col)
    for col in female_columns
]

male_left = [-value for value in male_population]
female_right = female_population

total_male = sum(male_population)
total_female = sum(female_population)
total_population = total_male + total_female

# 연령별 남녀 합계
age_population = [
    male_population[i] + female_population[i]
    for i in range(101)
]


# =========================================================
# 6. 핵심 지표 계산
# =========================================================

# 평균연령: 연령별 인구를 가중치로 사용합니다.
# 100세 이상은 계산상 100세로 처리합니다.
if total_population > 0:
    average_age = (
        sum(ages[i] * age_population[i] for i in range(101))
        / total_population
    )
else:
    average_age = 0.0

# 고령화율: 전체 인구 중 65세 이상 인구의 비율
elderly_population = sum(age_population[65:101])

if total_population > 0:
    aging_rate = elderly_population / total_population * 100
else:
    aging_rate = 0.0

# 아동 인구: 0~14세
child_population = sum(age_population[0:15])

# 비교 결과에 사용할 비율
if total_population > 0:
    child_rate = child_population / total_population * 100
else:
    child_rate = 0.0


# =========================================================
# 7. 지표 카드 3개
# =========================================================

st.divider()

st.subheader(
    f"📊 {selected_sido} {selected_sigungu} {selected_dong}"
)

st.caption(
    f"기준 연도: {latest_year}년 · 데이터에 포함된 최신 연도"
)

metric1, metric2, metric3 = st.columns(3)

with metric1:
    st.metric(
        label="👥 총인구",
        value=f"{total_population:,}명",
        help="남자 인구와 여자 인구의 합계입니다."
    )

with metric2:
    st.metric(
        label="🎂 평균연령",
        value=f"{average_age:.1f}세",
        help=(
            "연령별 인구를 가중치로 계산한 평균입니다. "
            "100세 이상은 계산상 100세로 처리합니다."
        )
    )

with metric3:
    # 20% 초과일 때만 주의 표시
    aging_warning = " ⚠️ 주의" if aging_rate > 20 else ""

    st.metric(
        label=f"👵 고령화율{aging_warning}",
        value=f"{aging_rate:.1f}%",
        delta=(
            "20% 초과 · 고령화 주의"
            if aging_rate > 20
            else "20% 이하"
        ),
        delta_color="inverse",
        help="전체 인구 중 65세 이상 인구가 차지하는 비율입니다."
    )

if aging_rate > 20:
    st.warning(
        f"고령화율이 {aging_rate:.1f}%로 20%를 초과합니다. "
        "고령 인구 비중이 높은 지역입니다."
    )


# =========================================================
# 8. 인구 피라미드 그리기
# =========================================================

fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=male_left,
        y=age_labels,
        orientation="h",
        name="남자",
        marker_color="#D9826B",
        customdata=male_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "남자 인구: %{customdata:,}명"
            "<extra></extra>"
        )
    )
)

fig.add_trace(
    go.Bar(
        x=female_right,
        y=age_labels,
        orientation="h",
        name="여자",
        marker_color="#E9B66B",
        customdata=female_population,
        hovertemplate=(
            "나이: %{y}<br>"
            "여자 인구: %{customdata:,}명"
            "<extra></extra>"
        )
    )
)

max_population = max(
    max(male_population, default=0),
    max(female_population, default=0),
    1
)

axis_limit = max_population * 1.1
tick_step = max(1, int(np.ceil(axis_limit / 5)))

tick_values_positive = list(
    range(0, int(axis_limit) + tick_step, tick_step)
)

tick_values_positive = [
    value for value in tick_values_positive
    if value <= axis_limit
]

if not tick_values_positive or tick_values_positive[0] != 0:
    tick_values_positive.insert(0, 0)

tick_values = (
    [-value for value in reversed(tick_values_positive) if value != 0]
    + [0]
    + [value for value in tick_values_positive if value != 0]
)

tick_text = [f"{abs(value):,}" for value in tick_values]

fig.update_layout(
    title={
        "text": f"{selected_dong} 연령별 남녀 인구",
        "x": 0.5,
        "xanchor": "center"
    },
    barmode="overlay",
    bargap=0.12,
    height=1000,
    plot_bgcolor="#FFFDF9",
    paper_bgcolor="#FFF9F2",
    font={
        "family": "Arial, sans-serif",
        "size": 12,
        "color": "#5D4037"
    },
    legend={
        "title": "성별",
        "orientation": "h",
        "yanchor": "bottom",
        "y": 1.02,
        "xanchor": "center",
        "x": 0.5
    },
    xaxis={
        "title": "인구 (명)",
        "range": [-axis_limit, axis_limit],
        "tickmode": "array",
        "tickvals": tick_values,
        "ticktext": tick_text,
        "zeroline": True,
        "zerolinecolor": "#9E8A7C",
        "zerolinewidth": 1.5,
        "gridcolor": "#F0E4D8"
    },
    yaxis={
        "title": "나이",
        "categoryorder": "array",
        "categoryarray": age_labels,
        "autorange": True,
        "showgrid": False,
        "tickfont": {"size": 10}
    },
    margin={"l": 100, "r": 40, "t": 100, "b": 70}
)

st.plotly_chart(
    fig,
    width="stretch",
    config={"displayModeBar": True}
)


# =========================================================
# 9. 동네 인구 구성 자동 설명
# =========================================================

st.subheader("💬 우리 동네 인구 한 줄 분석")

if total_population == 0:
    insight = (
        "인구 자료가 없어 아이와 어르신의 비중을 "
        "비교할 수 없습니다."
    )
elif child_population > elderly_population:
    insight = (
        f"이 동네는 아이가 많은 편이에요! "
        f"0~14세 인구는 {child_population:,}명({child_rate:.1f}%), "
        f"65세 이상 인구는 {elderly_population:,}명입니다."
    )
elif child_population < elderly_population:
    insight = (
        f"이 동네는 어르신이 많은 편이에요. "
        f"65세 이상 인구는 {elderly_population:,}명으로, "
        f"0~14세 인구 {child_population:,}명보다 많습니다."
    )
else:
    insight = (
        f"이 동네는 아이와 어르신의 인구가 같아요. "
        f"각각 {child_population:,}명입니다."
    )

st.markdown(
    f'<div class="insight-card">{insight}</div>',
    unsafe_allow_html=True
)


# =========================================================
# 10. 연령별 인구 표
# =========================================================

with st.expander("📋 연령별 인구 표 보기"):
    population_table = pd.DataFrame({
        "나이": age_labels,
        "남자 인구": male_population,
        "여자 인구": female_population,
        "합계": age_population
    })

    st.dataframe(
        population_table,
        hide_index=True,
        width="stretch"
    )

st.caption(
    "자료: 제공된 연도별 읍·면·동 인구 CSV | "
    "남자는 왼쪽, 여자는 오른쪽에 표시됩니다. "
    "고령화율은 65세 이상 인구 비율이며, "
    "평균연령은 100세 이상을 100세로 계산합니다."
)
