
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# Set the page title
st.set_page_config(page_title="Enh Basic Dashboard", layout="wide")

#### GENERATING A SIMPLE DATASET ####
# Create a sample dataset
np.random.seed(42)  # For reproducibility

data_db = pd.DataFrame({
    "Category": np.random.choice(["A", "B", "C", "D"], size=100),
    "Value": np.random.randint(10, 100, size=100),
    "Date": pd.date_range(start="2024-01-01", periods=100, freq="D")
})
data_db.head()

#### SETTING UP DASHBOARD LAYOUT ####

# Title and description
st.markdown("<h1 style='text-align: center; color: lightblue;'> Enhanced-customised Data Dashboard</h1>", unsafe_allow_html=True)
#Customize the Title with Markdown

# change the font
#Alternative Fonts: 'Arial', 'Courier New', 'Verdana', 'Georgia'
st.markdown(
    """
    <style>
    * {
        font-family: 'Comic Sans MS', cursive, sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True
)

#Displays a company logo
import os
script_dir = os.path.dirname(os.path.abspath(__file__))
logo_path = os.path.join(script_dir, "logo.png")
st.sidebar.image(logo_path, caption="Company Logo")
#st.sidebar.image("logo.png", caption="Company Logo")

# Stylized filter header
st.sidebar.markdown("<h3 style='color: purple;'>Filters</h3>", unsafe_allow_html=True) #customised 

#adjust sidebar width
st.markdown(
    """
    <style>
        [data-testid="stSidebar"] {
            min-width: 200px;
            max-width: 300px;
        }
    </style>
    """,
    unsafe_allow_html=True
)

category_filter = st.sidebar.multiselect("Select Category", options=data_db["Category"].unique(), default=data_db["Category"].unique())

date_range = st.sidebar.date_input(
    "Select Date Range",
    [data_db["Date"].min(), data_db["Date"].max()],
    min_value=data_db["Date"].min(),
    max_value=data_db["Date"].max()
)

#Display a Summary of Selected Data
st.sidebar.write(f"📌 {len(category_filter)} categories selected")
st.sidebar.write(f"📌 Date range: {date_range[0]} - {date_range[1]}")

filtered_data = data_db[
    (data_db["Category"].isin(category_filter)) & 
    (data_db["Date"] >= pd.to_datetime(date_range[0])) & 
    (data_db["Date"] <= pd.to_datetime(date_range[1]))
]

# Create two columns
col1, col2 = st.columns(2)  
with col1:
    st.metric("Total Records", len(filtered_data))
#this will be displayed in col1
with col2:
    st.metric("Average Value", round(filtered_data["Value"].mean(), 2))
#this will be displayed in col2

#Add an Interactive Progress Bar
progress = st.progress(0)
for percent_complete in range(100):
    progress.progress(percent_complete + 1)

#Download Button for Filtered Data
st.download_button("Download Data", data=filtered_data.to_csv(), file_name="filtered_data.csv", mime="text/csv")

#Dark Mode Toggle

dark_mode1 = st.sidebar.checkbox("Enable Dark Mode")
if dark_mode1:
    st.markdown(
        """
        <style>
        .stApp {background-color: #1E1E1E; color: white;}
        </style>
        """,
        unsafe_allow_html=True
    )
                
dark_mode = st.sidebar.toggle("Dark Mode", value=False)  # Default is Light Mode

# Apply Dark Mode Styles if Toggle is Enabled
if dark_mode:
    st.markdown(
        """
        <style>
            .stApp {
                background-color: #1E1E1E;
                color: white;
            }
            [data-testid="stSidebar"] {
                background-color: #333333;
            }
            h1, h2, h3, h4, h5, h6, p, label {
                color: white;
            }
        </style>
        """,
        unsafe_allow_html=True
    )


#Add a Loading Spinner
with st.spinner("Loading data..."):
    import time
    time.sleep(2)
    
# Set a Custom Sidebar Background Color
st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: lightblue;
    }
    </style>
""", unsafe_allow_html=True)

# Table Display Using Data Editor
edited_data = st.data_editor(filtered_data, num_rows="dynamic")

# Add a Sidebar Search Box
search_text = st.sidebar.text_input("Search Category")
filtered_data = filtered_data[filtered_data["Category"].str.contains(search_text, case=False, na=False)]

# Enable dynamic data display.
num_records = st.sidebar.slider("Number of Records", min_value=10, max_value=100, value=50, step=10)
filtered_data = filtered_data.head(num_records)

#Add a Color Picker
chart_color = st.sidebar.color_picker("Pick a Chart Color", "#3498db")

#add some text to sidebar 
text = ("This project was supported by XYZ")
st.sidebar.info(text)

#Display a Random Fun Fact
fun_facts = [
    "Fun fact: The world's largest desert is Antarctica!",
    "Fun fact: Honey never spoils.",
    "Fun fact: Bananas are berries, but strawberries aren't!"
]
st.sidebar.info(np.random.choice(fun_facts))

#add theme selector
theme = st.sidebar.radio("Choose Theme", ["Light", "Dark", "Blue"])
if theme == "Dark":
    st.markdown('<style>.stApp {background-color: black; color: white;}</style>', unsafe_allow_html=True)
elif theme == "Blue":
    st.markdown('<style>.stApp {background-color: #3498db; color: white;}</style>', unsafe_allow_html=True)

#

#### PLOTS ####
fig_bar = px.bar(filtered_data.groupby("Category")["Value"].mean().reset_index(),
                 x="Category", y="Value", title="Average Value by Category",
                 color="Category", text_auto=True, color_discrete_sequence=[chart_color])
st.plotly_chart(fig_bar, theme="streamlit", use_container_width=True)

fig_line = px.line(filtered_data, x="Date", y="Value", title="Value Trend Over Time", markers=True, color_discrete_sequence=[chart_color])
st.plotly_chart(fig_line, theme="streamlit", use_container_width=True)

fig_box = px.box(filtered_data, x="Category", y="Value", title="Value Distribution by Category", color_discrete_sequence=[chart_color])
st.plotly_chart(fig_box, theme="streamlit", use_container_width=True)

fig_scatter = px.scatter(filtered_data, x="Date", y="Value", color="Category",
                         title="Scatter Plot of Value Over Time", size_max=10,
                         color_discrete_sequence=[chart_color])
st.plotly_chart(fig_scatter)

#Add an Expandable FAQ Section
with st.expander("📌 How to Use This Dashboard"):
    st.write("This dashboard allows you to visualize data interactively.")

#Add a Footer with 
st.markdown(
    """
    <style>
        .footer {
            position: fixed;
            left: 0;
            bottom: 0;
            width: 100%;
            text-align: center;
            font-size: 14px;
            color: gray;
            background-color: #013220;  /* Match the background color of your app */
            padding: 10px 0;  /* Adds some space inside the footer */
            z-index: 9999; /* Keeps the footer on top of other elements */
        }
        .stApp {
            padding-bottom: 50px; /* Creates space at the bottom so content doesn't hide behind footer */
        }
    </style>
    <div class="footer">© 2025 My Dashboard</div>
    """,
    unsafe_allow_html=True
)
