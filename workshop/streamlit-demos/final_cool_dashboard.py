import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Set the page title
st.set_page_config(page_title="Cooler Dashboard", layout="wide")

# Remove whitespace from the top of the page and sidebar

st.markdown("""
<style>
header.stAppHeader {
    background-color: transparent;
}
section.stMain .block-container {
    padding-top: 0rem;
    z-index: 1;
}
</style>""", unsafe_allow_html=True)


hide_streamlit_style = """
                <style>
                div[data-testid="stToolbar"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                div[data-testid="stDecoration"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                div[data-testid="stStatusWidget"] {
                visibility: hidden;
                height: 0%;
                position: fixed;
                }
                #MainMenu {
                visibility: hidden;
                height: 0%;
                }
                header {
                visibility: hidden;
                height: 0%;
                }
                footer {
                visibility: hidden;
                height: 0%;
                }
                </style>
                """
st.markdown(hide_streamlit_style, unsafe_allow_html=True)


# Custom CSS for Dark Green Background and White Text
st.markdown(
    """
    <style>
        .stApp {
            background-color: #013220;
            color: white;
        }
        /* Styling for category filter and date range */
        div.stMultiSelect label, div.stDateInput label {
            color: white !important;
        }
        div[data-baseweb="tag"] {
            background-color: green !important;
            color: yellow !important;
        }
        .plotly-text {
            color: darkyellow !important;
        }
    </style>
    """,
    unsafe_allow_html=True
)



# Create a sample dataset
np.random.seed(42)
data_db = pd.DataFrame({
    "Category": np.random.choice(["A", "B", "C", "D"], size=100),
    "Value": np.random.randint(10, 100, size=100),
    "Date": pd.date_range(start="2024-01-01", periods=100, freq="D")
})

# Title
st.markdown("<h1 style='text-align: center; color: white;'>Cool Data Dashboard</h1>", unsafe_allow_html=True)

st.markdown(
    """
    <p style='text-align: center; color: white; font-size: 24px;'>
    by Name Surname
    </p>
    """,
    unsafe_allow_html=True
)
st.markdown(
    """
    <p style='text-align: center; color: white; font-size: 20px;'>
    Text text text Text text text Text text text Text text text Text text text Text text text Text text text Text text text
    Text text text Text text text Text text text Text text text Text text text Text text text Text text text Text text text
    </p>
    """,
    unsafe_allow_html=True
)

# Category Filter Below Title
#category_filter = st.multiselect("Select Category", options=data_db["Category"].unique(), default=data_db["Category"].unique())
#date_range = st.date_input("Select Date Range", [data_db["Date"].min(), data_db["Date"].max()], min_value=data_db["Date"].min(), max_value=data_db["Date"].max())

# Create two columns for Category and Date Range selectors
col1, col2 = st.columns([1, 1])  # Adjust the width ratio here if needed
with col1:
    # Category Filter
    category_filter = st.multiselect("Select Category", options=data_db["Category"].unique(), default=data_db["Category"].unique())
    
with col2:
    # Date Range Filter
    date_range = st.date_input("Select Date Range", [data_db["Date"].min(), data_db["Date"].max()], min_value=data_db["Date"].min(), max_value=data_db["Date"].max())


filtered_data = data_db[
    (data_db["Category"].isin(category_filter)) & 
    (data_db["Date"] >= pd.to_datetime(date_range[0])) & 
    (data_db["Date"] <= pd.to_datetime(date_range[1]))
]

# Dark Yellow Data in Plots
fig_bar = px.bar(filtered_data.groupby("Category")["Value"].mean().reset_index(), x="Category", y="Value", title="Average Value by Category", text_auto=True, color_discrete_sequence=["#FFD700"])
fig_bar.update_layout(
    title=dict(
        x=0.5,  # Center the title horizontally
        xanchor="center",  # Center title horizontally
    )
)

fig_line = px.line(filtered_data, x="Date", y="Value", title="Value Trend Over Time", markers=True, color_discrete_sequence=["#FFD700"])
fig_line.update_layout(
    title=dict(
        x=0.5,  # Center the title horizontally
        xanchor="center",  # Center title horizontally
    )
)

fig_box = px.box(filtered_data, x="Category", y="Value", title="Value Distribution by Category", color_discrete_sequence=["#FFD700"])
fig_box.update_layout(
    title=dict(
        x=0.5,  # Center the title horizontally
        xanchor="center",  # Center title horizontally
    )
)

color_map = {
    "A": "#FFD700",  # Gold
    "B": "#FFCC00",  # Amber
    "C": "#FFB800",  # Yellow Orange
    "D": "#FF9900"   # Dark Yellow
}
fig_scatter = px.scatter(filtered_data, x="Date", y="Value",
                         color_discrete_map=color_map,
                         color="Category", title="Scatter Plot of Value Over Time", size_max=10, color_discrete_sequence=["#FFD700"], symbol="Category")
fig_scatter.update_layout(
    title=dict(
        x=0.5,  # Center the title horizontally
        xanchor="center",  # Anchor title in the center
    ),
    legend=dict(
        orientation="h",  # Horizontal orientation for the legend
        yanchor="bottom",  # Align the legend at the bottom of the legend box
        y=0.97,  # Position the legend just below the title
        xanchor="center",  # Center the legend horizontally
        x=0.45,
        title=None
    ),
    margin=dict(t=80),  # Adjust top margin to make space for the title and legend
)
# Display Plots in 2x2 Grid
col1, col2 = st.columns(2)
with col1:
    st.plotly_chart(fig_bar, use_container_width=True)
    st.write("\n".join(np.random.choice(["Text text text Text text textText text text Text text text Text text text Text text text Text text text Text text text Text text text Text text text"], 4)))
    
    st.plotly_chart(fig_box, use_container_width=True)
    st.write("\n".join(np.random.choice(["Text text text Text text textText text text Text text text Text text text Text text text Text text text Text text text Text text text Text text text"], 4)))

with col2:
    st.plotly_chart(fig_line, use_container_width=True)
    st.write("\n".join(np.random.choice(["Text text text Text text textText text text Text text text Text text text Text text text Text text text Text text text Text text text Text text text"], 4)))
    
    st.plotly_chart(fig_scatter, use_container_width=True)
    st.write("\n".join(np.random.choice(["Text text text Text text textText text text Text text text Text text text Text text text Text text text Text text text Text text text Text text text"], 4)))

# Footer
st.markdown(
    """
    <style>
        /* Footer Styling */
        .footer {
            position: static;
            bottom: 0;
            left: 0;
            width: 100%;
            text-align: center;
            font-size: 14px;
            color: rgba(255, 255, 255, 0.4);  /* White color with slight transparency */
            background-color: #013220;  /* Background color matching the app's theme */
            padding: 10px 0;  /* Add space inside the footer */
            z-index: 1000; /* Ensure it stays on top of other elements */
        }
        
        /* Add padding to main content so it doesn't overlap with footer */
        .stApp {
            padding-bottom: 40px;  /* Space for the footer */
        }
    </style>
    <div class="footer">© 2025 My Dashboard</div>
    """,
    unsafe_allow_html=True
)

