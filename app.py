import streamlit as st
import pyomo.environ as aml
from pyomo.opt import SolverFactory
import pandas as pd
import plotly.graph_objects as go

# 1. 앱 제목 및 설정
st.set_page_config(page_title="APP 최적화 시스템", layout="wide")
st.title("원예장비 제조업체 총괄생산계획(APP) 수립")

# 2. 사이드바: 파라미터 입력 (PDF 데이터 기준)
with st.sidebar:
    st.header("운영 비용 파라미터")
    # PDF [cite: 1181-1182] 기준 기본값 설정
    reg_wage = st.number_input("정규임금 (천원/시간)", value=4)
    ot_wage = st.number_input("초과임금 (천원/시간)", value=6)
    hire_cost = st.number_input("고용비용 (천원/인)", value=300)
    fire_cost = st.number_input("해고비용 (천원/인)", value=500)
    hold_cost = st.number_input("재고유지비 (천원/개/월)", value=2)
    back_cost = st.number_input("부재고비용 (천원/개/월)", value=5)
    mat_cost = st.number_input("원자재비 (천원/개)", value=10)

# 3. 메인 화면: 수요 입력
st.subheader("6개월 수요 예측 입력")
demand_input = st.text_input("쉼표로 구분하여 입력", "1600, 3000, 3200, 3800, 2200, 2200")
D = [int(x.strip()) for x in demand_input.split(",")]

# 4. 최적화 로직 (PDF 5~6페이지 수식 반영)
def solve_app(D_list):
    model = aml.ConcreteModel()
    T = range(1, len(D_list) + 1)
    TIME = range(0, len(D_list) + 1)

    # 결정변수 정의 [cite: 1262-1282]
    model.W = aml.Var(TIME, domain=aml.NonNegativeReals) # 작업자 수
    model.H = aml.Var(T, domain=aml.NonNegativeReals)    # 고용
    model.L = aml.Var(T, domain=aml.NonNegativeReals)    # 해고
    model.P = aml.Var(T, domain=aml.NonNegativeReals)    # 생산량
    model.I = aml.Var(TIME, domain=aml.NonNegativeReals) # 재고
    model.S = aml.Var(TIME, domain=aml.NonNegativeReals) # 부재고
    model.O = aml.Var(T, domain=aml.NonNegativeReals)    # 잔업시간

    # 목적함수: 총 비용 최소화 [cite: 1294, 1296, 1298]
    model.cost = aml.Objective(expr=sum(
        (80*8*reg_wage)*model.W[t] + ot_wage*model.O[t] + 
        hire_cost*model.H[t] + fire_cost*model.L[t] +
        hold_cost*model.I[t] + back_cost*model.S[t] + 
        mat_cost*model.P[t] for t in T), sense=aml.minimize)

    # 제약조건 [cite: 1312, 1317, 1326, 1349]
    model.cons = aml.ConstraintList()
    model.W[0].fix(80)   # 초기 인원 80명 [cite: 1226]
    model.I[0].fix(1000) # 초기 재고 1000개 [cite: 1227]
    model.S[0].fix(0)    # 초기 부재고 0 [cite: 1229]

    for t in T:
        model.cons.add(model.W[t] == model.W[t-1] + model.H[t] - model.L[t])
        model.cons.add(model.P[t] <= 40*model.W[t] + 0.25*model.O[t])
        model.cons.add(model.I[t] == model.I[t-1] + model.P[t] - D_list[t-1] - model.S[t-1] + model.S[t])
        model.cons.add(model.O[t] <= 10*model.W[t])
    
    model.cons.add(model.I[len(D_list)] >= 500) # 최종 재고 500개 이상 [cite: 1228]
    model.cons.add(model.S[len(D_list)] == 0)   # 최종 부재고 0 [cite: 1231]

    SolverFactory('glpk').solve(model)
    return model

# 5. 실행 및 결과 출력
if st.button("최적화 실행"):
    res = solve_app(D)
    
    # 데이터 프레임 생성
    res_data = {
        "월": [f"{t}월" for t in range(1, len(D)+1)],
        "생산량(P)": [round(res.P[t](), 1) for t in range(1, len(D)+1)],
        "재고(I)": [round(res.I[t](), 1) for t in range(1, len(D)+1)],
        "부재고(S)": [round(res.S[t](), 1) for t in range(1, len(D)+1)],
        "인원(W)": [round(res.W[t](), 1) for t in range(1, len(D)+1)]
    }
    df = pd.DataFrame(res_data)

    col1, col2 = st.columns([1, 2])
    with col1:
        st.metric("최소 총 비용", f"{res.cost():,.0f} 천원")
        st.table(df)

    with col2:
        # 동적 차트 생성
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df["월"], y=D, name="수요 예측", marker_color='lightgrey'))
        fig.add_trace(go.Scatter(x=df["월"], y=df["생산량(P)"], name="최적 생산량", line=dict(color='blue', width=3)))
        fig.update_layout(title="수요 대비 최적 생산 계획", barmode='group')
        st.plotly_chart(fig)