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
    
    while dots_per_row.sum() < total_seats: dots_per_row[-1] += 1
    while dots_per_row.sum() > total_seats: dots_per_row[-1] -= 1
        
    points = []
    for r, dots in zip(radii, dots_per_row):
        angles = np.linspace(np.pi, 0, dots)
        for theta in angles:
            points.append((r * np.cos(theta), r * np.sin(theta)))
    return points

# --- Fallback Data (If the server blocks us) ---
def get_fallback_data():
    st.warning("⚠️ The Election Commission server blocked the live request. Displaying estimated fallback data instead.")
    df_fptp = pd.DataFrame({
        "Party": ["Nepali Congress", "Nepal Communist Party (UML)", "Nepali Communist Party", "Rastriya Swatantra Party", "Rastriya Prajatantra Party", "Janata Samajwadi Party, Nepal"],
        "Direct Seats": [57, 44, 18, 7, 7, 7]
    })
    
    df_pr = pd.DataFrame({
        "Party": ["Rastriya Swatantra Party", "Nepali Congress", "Nepal Communist Party (UML)", "Nepali Communist Party", "Rastriya Prajatantra Party", "Janata Samajwadi Party, Nepal"],
        "PR Seats": [58, 19, 16, 9, 4, 4] # Based on your earlier 110 seat calculation
    })
    
    df_combined = pd.merge(df_fptp, df_pr, on="Party", how="outer").fillna(0)
    df_combined["Total Seats"] = df_combined["Direct Seats"] + df_combined["PR Seats"]
    df_combined = df_combined.sort_values(by="Total Seats", ascending=False).reset_index(drop=True)
    return df_combined, 10012792 # Returning the combined dataframe and dummy total votes

# --- Data Fetching & Processing ---
@st.cache_data(ttl=300)
def fetch_all_election_data():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        # 1. Fetch Direct (FPTP) Data
        fptp_url = "https://result.election.gov.np/"
        fptp_resp = requests.get(fptp_url, headers=headers, timeout=15)
        
        if "<table" not in fptp_resp.text.lower():
            return get_fallback_data() # Server didn't send tables, use fallback
            
        fptp_tables = pd.read_html(fptp_resp.text, flavor='lxml')
        df_fptp = fptp_tables[0]
        df_fptp = df_fptp.rename(columns={df_fptp.columns[1]: "Party", df_fptp.columns[2]: "Direct Seats"})
        df_fptp["Direct Seats"] = df_fptp["Direct Seats"].apply(clean_nepali_numbers)
        df_fptp["Direct Seats"] = pd.to_numeric(df_fptp["Direct Seats"], errors='coerce').fillna(0)
        df_fptp = df_fptp[["Party", "Direct Seats"]]

        # 2. Fetch PR Data
        pr_url = "https://result.election.gov.np/PRVoteChartResult2082.aspx"
        pr_resp = requests.get(pr_url, headers=headers, timeout=15)
        
        if "<table" not in pr_resp.text.lower():
            return get_fallback_data() # Server didn't send tables, use fallback

        pr_tables = pd.read_html(pr_resp.text, flavor='lxml')
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
        df_combined = pd.merge(df_fptp, df_pr_results, on="Party", how="outer").fillna(0)
        df_combined["Total Seats"] = df_combined["Direct Seats"] + df_combined["PR Seats"]
        df_combined = df_combined[df_combined["Total Seats"] > 0]
        df_combined = df_combined.sort_values(by="Total Seats", ascending=False).reset_index(drop=True)
        
        return df_combined, total_votes

    except Exception as e:
        print(f"Scraping Error: {e}")
        return get_fallback_data() # If anything crashes, catch it and load fallback data!

# --- User Interface ---
st.title("🇳🇵 Live Nepal Parliament Dashboard")
st.write("Aggregates Direct (FPTP) results and Proportional Representation (PR) calculations to visualize the full 275-seat Pratinidhi Sabha.")

if st.button("🔴 Fetch Live Election Data", type="primary"):
    with st.spinner("Scraping and calculating from Election Commission portals..."):
        df_final, total_valid_votes = fetch_all_election_data()
    
    st.success("Dashboard successfully updated!")
    
    # Display Summary Metrics
    st.subheader("Data Summary")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Parliament Seats", int(df_final["Total Seats"].sum()))
    m2.metric("Direct Seats Decided", int(df_final["Direct Seats"].sum()))
    m3.metric("PR Seats Allocated", int(df_final["PR Seats"].sum()))

    st.divider()
    
    # --- Parliament Dot Visualization ---
    st.subheader("Parliamentary Composition")
    
    # Custom Party Colors Dictionary
    party_colors = {
        "Nepal Communist Party (UML)": "#e74c3c",       # Red
        "Nepali Communist Party": "#c0392b",            # Dark Red
        "Nepali Congress": "#27ae60",                   # Green
        "Rastriya Swatantra Party": "#3498db",          # Blue
        "Rastriya Prajatantra Party": "#f1c40f",        # Yellow
        "Janata Samajwadi Party, Nepal": "#e67e22",     # Orange
        "Shram Sanskriti Party": "#9b59b6"              # Purple
    }
    
    total_seats = int(df_final["Total Seats"].sum())
    points = generate_parliament_coordinates(total_seats)
    
    x_coords, y_coords, text_labels, color_labels = [], [], [], []
    
    point_idx = 0
    for _, row in df_final.iterrows():
        seats = int(row["Total Seats"])
        for _ in range(seats):
            if point_idx < len(points):
                x_coords.append(points[point_idx][0])
                y_coords.append(points[point_idx][1])
                text_labels.append(f"{row['Party']}<br>Direct: {int(row['Direct Seats'])} | PR: {int(row['PR Seats'])}<br>Total: {seats}")
                
                # Assign custom color if it exists, otherwise default to grey
                color = party_colors.get(row['Party'], "#95a5a6") 
                color_labels.append(color)
                point_idx += 1

    # Create Plotly Chart
    fig = go.Figure()
    
    # We group dots by color so the legend works properly
    unique_parties = df_final['Party'].unique()
    for party in unique_parties:
        idx = [i for i, p in enumerate(df_final['Party']) if p == party]
        # Get the color for this specific party
        p_color = party_colors.get(party, "#95a5a6")
        
        # Find which coordinates belong to this party
        party_x = [x_coords[i] for i, label in enumerate(text_labels) if party in label]
        party_y = [y_coords[i] for i, label in enumerate(text_labels) if party in label]
        party_text = [text_labels[i] for i, label in enumerate(text_labels) if party in label]
        
        if party_x:
            fig.add_trace(go.Scatter(
                x=party_x,
                y=party_y,
                mode='markers',
                name=party,
                text=party_text,
                hoverinfo='text',
                marker=dict(size=14, color=p_color, line=dict(width=1, color='white'))
            ))

    fig.update_layout(
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
        height=550,
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.divider()
    
    # --- Detailed Table ---
    st.subheader("Detailed Seat Breakdown")
    st.dataframe(df_final, use_container_width=True, hide_index=True)
