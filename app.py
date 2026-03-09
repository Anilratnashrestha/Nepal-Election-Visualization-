import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import math

# --- Page Configuration ---
st.set_page_config(page_title="Nepal Election Dashboard", page_icon="🇳🇵", layout="wide")

# --- Parliament Coordinate Generator ---
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

# --- Core Election Data & Calculation ---
@st.cache_data
def load_and_calculate_data():
    # 1. Direct (FPTP) Data from your image (164 decided + 1 undecided)
    df_fptp = pd.DataFrame({
        "Party": [
            "Rastriya Swatantra Party", "Nepali Congress", "Nepal Communist Party (UML)", 
            "Nepali Communist Party", "Shram Sanskriti Party", "Rastriya Prajatantra Party", 
            "Independent", "Undecided"
        ],
        "Direct Seats": [125, 18, 9, 7, 3, 1, 1, 1]
    })

    # 2. PR Votes Data from your earlier image
    df_pr_votes = pd.DataFrame({
        "Party": [
            "Rastriya Swatantra Party", "Nepali Congress", "Nepal Communist Party (UML)", 
            "Nepali Communist Party", "Shram Sanskriti Party", "Rastriya Prajatantra Party", 
            "Janata Samajwadi Party, Nepal"
        ],
        "Votes": [4815473, 1621264, 1349624, 733964, 341095, 315870, 164895]
    })

    # 3. Calculate PR Seats (110 Total) based on Sainte-Laguë (1.2 Divisor)
    total_votes = df_pr_votes["Votes"].sum()
    threshold = total_votes * 0.03
    df_eligible = df_pr_votes[df_pr_votes["Votes"] >= threshold].copy()
    
    total_pr_seats = 110
    party_pr_seats = {party: 0 for party in df_eligible["Party"]}
    
    for _ in range(total_pr_seats):
        quotients = []
        for _, row in df_eligible.iterrows():
            p = row["Party"]
            seats_won = party_pr_seats[p]
            divisor = 1.2 if seats_won == 0 else (2 * seats_won + 1)
            quotients.append((p, row["Votes"] / divisor))
            
        winner = max(quotients, key=lambda x: x[1])[0]
        party_pr_seats[winner] += 1
        
    df_pr_calculated = pd.DataFrame(list(party_pr_seats.items()), columns=["Party", "PR Seats"])

    # 4. Merge Direct and PR Results
    df_final = pd.merge(df_fptp, df_pr_calculated, on="Party", how="outer").fillna(0)
    df_final["Total Seats"] = df_final["Direct Seats"] + df_final["PR Seats"]
    df_final = df_final[df_final["Total Seats"] > 0]
    
    # Sort to place Undecided at the end, and sort the rest by Total Seats
    df_undecided = df_final[df_final["Party"] == "Undecided"]
    df_decided = df_final[df_final["Party"] != "Undecided"].sort_values(by="Total Seats", ascending=False)
    
    df_combined = pd.concat([df_decided, df_undecided]).reset_index(drop=True)
    return df_combined

# --- User Interface ---
st.title("🇳🇵 Live Nepal Parliament Dashboard")
st.write("Visualizing the 275-seat Pratinidhi Sabha (165 Direct FPTP + 110 PR).")

df_final = load_and_calculate_data()

# Display Summary Metrics
st.subheader("Data Summary")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Parliament Seats", int(df_final["Total Seats"].sum()))
m2.metric("Direct Seats Decided", int(df_final[df_final["Party"] != "Undecided"]["Direct Seats"].sum()))
m3.metric("PR Seats Allocated", int(df_final["PR Seats"].sum()))
m4.metric("Undecided Direct Seats", 1)

st.divider()

# --- Parliament Dot Visualization ---
st.subheader("Parliamentary Composition (275 Seats)")

# Color Palette Mapping
party_colors = {
    "Rastriya Swatantra Party": "#3498db",          # Blue
    "Nepali Congress": "#27ae60",                   # Green
    "Nepal Communist Party (UML)": "#e74c3c",       # Red
    "Nepali Communist Party": "#c0392b",            # Dark Red
    "Shram Sanskriti Party": "#9b59b6",             # Purple
    "Rastriya Prajatantra Party": "#f1c40f",        # Yellow
    "Independent": "#34495e",                       # Dark Grey
    "Undecided": "#ecf0f1"                          # Light Grey/White
}

total_seats = int(df_final["Total Seats"].sum())
points = generate_parliament_coordinates(total_seats)

x_coords, y_coords, text_labels, color_labels, line_colors = [], [], [], [], []

point_idx = 0
for _, row in df_final.iterrows():
    seats = int(row["Total Seats"])
    for _ in range(seats):
        if point_idx < len(points):
            x_coords.append(points[point_idx][0])
            y_coords.append(points[point_idx][1])
            
            # Custom hovering text for the Undecided seat
            if row['Party'] == "Undecided":
                text_labels.append("<b>Undecided Seat</b><br>Awaiting Supreme Court's order/re-election")
                line_colors.append("#e74c3c") # Red border for undecided
            else:
                text_labels.append(f"<b>{row['Party']}</b><br>Direct: {int(row['Direct Seats'])} | PR: {int(row['PR Seats'])}<br>Total: {seats}")
                line_colors.append("white")
            
            color_labels.append(party_colors.get(row['Party'], "#95a5a6"))
            point_idx += 1

# Create Plotly Chart
fig = go.Figure()

unique_parties = df_final['Party'].unique()
for party in unique_parties:
    idx = [i for i, p in enumerate(df_final['Party']) if p == party]
    p_color = party_colors.get(party, "#95a5a6")
    
    party_x = [x_coords[i] for i, label in enumerate(text_labels) if party in label or (party=="Undecided" and "Undecided" in label)]
    party_y = [y_coords[i] for i, label in enumerate(text_labels) if party in label or (party=="Undecided" and "Undecided" in label)]
    party_text = [text_labels[i] for i, label in enumerate(text_labels) if party in label or (party=="Undecided" and "Undecided" in label)]
    party_line = [line_colors[i] for i, label in enumerate(text_labels) if party in label or (party=="Undecided" and "Undecided" in label)]
    
    if party_x:
        fig.add_trace(go.Scatter(
            x=party_x, y=party_y,
            mode='markers',
            name=party,
            text=party_text,
            hoverinfo='text',
            marker=dict(
                size=20, 
                color=p_color, 
                line=dict(width=1.5 if party == "Undecided" else 1, color=party_line)
            )
        ))

fig.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False, scaleanchor="x", scaleratio=1),
    height=550, margin=dict(l=20, r=20, t=20, b=20),
    legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5)
)

st.plotly_chart(fig, use_container_width=True)

# Caption specifically requested for the Undecided vote
st.caption("🚨 **Note:** 1 Direct (FPTP) seat remains **Undecided** pending a Supreme Court order or re-election. It is represented by the white dot with a red outline in the visualization.")

st.divider()

# --- Detailed Table ---
st.subheader("Detailed Seat Breakdown")
# Format columns to integers for a cleaner look
df_display = df_final.copy()
df_display["Direct Seats"] = df_display["Direct Seats"].astype(int)
df_display["PR Seats"] = df_display["PR Seats"].astype(int)
df_display["Total Seats"] = df_display["Total Seats"].astype(int)

st.dataframe(df_display, use_container_width=True, hide_index=True)

