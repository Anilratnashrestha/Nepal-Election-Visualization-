import streamlit as st
import pandas as pd
import requests
import numpy as np
import plotly.graph_objects as go
import math

# --- Page Configuration ---
st.set_page_config(page_title="Nepal Election Dashboard", page_icon="🇳🇵", layout="wide")

# --- Helper Functions ---
def clean_nepali_numbers(text):
    if pd.isna(text): return "0"
    text = str(text)
    nepali_to_english = {'०': '0', '१': '1', '२': '2', '३': '3', '४': '4', '५': '5', '६': '6', '७': '7', '८': '8', '९': '9', ',': '', ' ': ''}
    for nep, eng in nepali_to_english.items():
        text = text.replace(nep, eng)
    return text

def generate_parliament_coordinates(total_seats):
    """Calculates x, y coordinates to form concentric semicircles for the parliament plot."""
    rows = 8
    radii = np.linspace(1, 2, rows)
    circumferences = math.pi * radii
    dots_per_row = (circumferences / circumferences.sum() * total_seats).astype(int)
    
    # Adjust rounding errors to exactly match total_seats
    while dots_per_row.sum() < total_seats: dots_per_row[-1] += 1
    while dots_per_row.sum() > total_seats: dots_per_row[-1] -= 1
        
    points = []
    for r, dots in zip(radii, dots_per_row):
        angles = np.linspace(np.pi, 0, dots)
        for theta in angles:
            points.append((r * np.cos(theta), r * np.sin(theta)))
    return points

# --- Data Fetching & Processing ---
@st.cache_data(ttl=300)
def fetch_all_election_data():
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 1. Fetch Direct (FPTP) Data
    fptp_url = "https://result.election.gov.np/"
    fptp_resp = requests.get(fptp_url, headers=headers, timeout=15)
    fptp_tables = pd.read_html(fptp_resp.text)
    
    # Find the table containing FPTP results (looking for 'Elected' or 'Won')
    df_fptp = None
    for t in fptp_tables:
        col_str = str(t.columns).lower()
        if 'party' in col_str and ('elected' in col_str or 'won' in col_str or 'विजयी' in col_str):
            df_fptp = t
            break
            
    if df_fptp is None:
        # Fallback if specific headers aren't found, usually it's the first or second table
        df_fptp = fptp_tables[0] 
        
    df_fptp = df_fptp.rename(columns={df_fptp.columns[1]: "Party", df_fptp.columns[2]: "Direct Seats"})
    df_fptp["Direct Seats"] = df_fptp["Direct Seats"].apply(clean_nepali_numbers)
    df_fptp["Direct Seats"] = pd.to_numeric(df_fptp["Direct Seats"], errors='coerce').fillna(0)
    df_fptp = df_fptp[["Party", "Direct Seats"]]

    # 2. Fetch PR Data
    pr_url = "https://result.election.gov.np/PRVoteChartResult2082.aspx"
    pr_resp = requests.get(pr_url, headers=headers, timeout=15)
    pr_tables = pd.read_html(pr_resp.text)
    df_pr = pr_tables[0]
    
    df_pr = df_pr.rename(columns={df_pr.columns[1]: "Party", df_pr.columns[2]: "Votes"})
    df_pr['Votes'] = df_pr['Votes'].apply(clean_nepali_numbers)
    df_pr['Votes'] = pd.to_numeric(df_pr['Votes'], errors='coerce').fillna(0)
    df_pr = df_pr[df_pr['Votes'] > 0].copy()
    
    total_votes = df_pr["Votes"].sum()
    threshold = total_votes * 0.03
    df_eligible = df_pr[df_pr["Votes"] >= threshold].copy()
    
    # 3. Calculate PR Seats (110 total)
    total_pr_seats = 110
    party_seats = {party: 0 for party in df_eligible["Party"]}
    for _ in range(total_pr_seats):
        quotients = [(p, row["Votes"] / (1.2 if party_seats[p] == 0 else (2 * party_seats[p] + 1))) for _, row in df_eligible.iterrows() for p in [row["Party"]]]
        winner = max(quotients, key=lambda x: x[1])[0]
        party_seats[winner] += 1
        
    df_pr_results = pd.DataFrame(list(party_seats.items()), columns=["Party", "PR Seats"])
    
    # 4. Merge Data (Direct + PR)
    # Outer join to ensure parties that won Direct but no PR (or vice versa) are included
    df_combined = pd.merge(df_fptp, df_pr_results, on="Party", how="outer").fillna(0)
    df_combined["Total Seats"] = df_combined["Direct Seats"] + df_combined["PR Seats"]
    df_combined = df_combined[df_combined["Total Seats"] > 0]
    df_combined = df_combined.sort_values(by="Total Seats", ascending=False).reset_index(drop=True)
    
    return df_combined, total_votes

# --- User Interface ---
st.title("🇳🇵 Live Nepal Parliament Dashboard")
st.write("Aggregates Direct (FPTP) results and Proportional Representation (PR) calculations to visualize the full 275-seat Pratinidhi Sabha.")

if st.button("🔴 Fetch Live Election Data", type="primary"):
    try:
        with st.spinner("Scraping and calculating from Election Commission portals..."):
            df_final, total_valid_votes = fetch_all_election_data()
        
        st.success("Data successfully synchronized!")
        
        # Display Summary Metrics
        st.subheader("Data Summary")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Parliament Seats", int(df_final["Total Seats"].sum()))
        m2.metric("Direct Seats Decided", int(df_final["Direct Seats"].sum()))
        m3.metric("PR Seats Allocated", int(df_final["PR Seats"].sum()))

        st.divider()
        
        # --- Parliament Dot Visualization ---
        
        st.subheader("Parliamentary Composition")
        
        # Prepare data for plotting
        total_seats = int(df_final["Total Seats"].sum())
        points = generate_parliament_coordinates(total_seats)
        
        # Assign points to parties
        x_coords, y_coords, text_labels, color_labels = [], [], [], []
        
        point_idx = 0
        for _, row in df_final.iterrows():
            seats = int(row["Total Seats"])
            for _ in range(seats):
                if point_idx < len(points):
                    x_coords.append(points[point_idx][0])
                    y_coords.append(points[point_idx][1])
                    text_labels.append(f"{row['Party']}<br>Total: {seats} seats")
                    color_labels.append(row['Party'])
                    point_idx += 1

        # Create Plotly Chart
        fig = go.Figure()
        for party in df_final['Party'].unique():
            # Filter dots for this specific party
            idx = [i for i, p in enumerate(color_labels) if p == party]
            fig.add_trace(go.Scatter(
                x=[x_coords[i] for i in idx],
                y=[y_coords[i] for i in idx],
                mode='markers',
                name=party,
                text=[text_labels[i] for i in idx],
                hoverinfo='text',
                marker=dict(size=12, line=dict(width=1, color='white'))
            ))

        fig.update_layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
            height=500,
            margin=dict(l=20, r=20, t=20, b=20),
            legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        st.divider()
        
        # --- Detailed Table ---
        st.subheader("Detailed Seat Breakdown")
        st.dataframe(df_final, use_container_width=True, hide_index=True)

    except Exception as e:
        st.error(f"⚠️ An error occurred while fetching or processing data. \n\nDetails: {e}")