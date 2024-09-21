import streamlit as st
import pandas as pd
import datetime

# Load the Excel file containing tag information
excel_url = 'https://github.com/RishikeshMahadevan/FIXexplainer/raw/main/fixtagcleanattemp1.xlsx'
tag_info_df = pd.read_excel(excel_url)
tag_info_df['Tag'] = tag_info_df['Tag'].astype(str)

# Function to calculate checksum
def calculate_checksum(fix_message):
    return str(sum(ord(char) for char in fix_message) % 256).zfill(3)

# Function to create a FIX message
def create_fix_message(order_id, client_id, broker_id, seq_num, symbol, side, qty, price=None):
    fix_message = []
    fix_message.append(f"8=FIX.4.4")  # BeginString
    fix_message.append(f"9=XXX")  # BodyLength
    fix_message.append(f"35=D")  # MsgType
    fix_message.append(f"49={client_id}")  # SenderCompID
    fix_message.append(f"56={broker_id}")  # TargetCompID
    fix_message.append(f"34={seq_num}")  # MsgSeqNum
    fix_message.append(f"52={datetime.datetime.utcnow().strftime('%Y%m%d-%H:%M:%S')}")  # SendingTime
    fix_message.append(f"11={order_id}")  # ClOrdID
    fix_message.append(f"21=1")  # HandlInst
    fix_message.append(f"55={symbol}")  # Symbol
    fix_message.append(f"54={side}")  # Side
    fix_message.append(f"38={qty}")  # OrderQty
    
    if price:
        fix_message.append(f"40=2")  # OrdType: Limit
        fix_message.append(f"44={price}")  # Price
    else:
        fix_message.append(f"40=1")  # OrdType: Market

    fix_message.append(f"60={datetime.datetime.utcnow().strftime('%Y%m%d-%H:%M:%S')}")  # TransactTime
    fix_message.append("10=XXX")  # Checksum
    message = '\x01'.join(fix_message) + '\x01'  # Use SOH as separator
    body_length = len(message.split("35=D\x01")[1]) - 1
    message = message.replace("9=XXX", f"9={body_length}")
    checksum = calculate_checksum(message)
    message = message.replace("10=XXX", f"10={checksum}")
    return message

# Function to decode a single order from FIX message
def decode_fix_order(fix_message, user_separator=None):
    if user_separator:
        separator = user_separator
    else:
        # Use SOH or | as default separators
        separator = '\x01' if '\x01' in fix_message else '|'
    fields = fix_message.split(separator)
    
    output = []
    for field in fields:
        if '=' in field:
            tag, value = field.split('=', 1)
            tag_info = tag_info_df[tag_info_df['Tag'] == tag]
            name = tag_info['Name'].values[0] if not tag_info.empty else 'UnknownTag'
            description = tag_info['Description'].values[0] if not tag_info.empty else 'Description not available'
            output.append([tag, name, value, description])
    output_df = pd.DataFrame(output, columns=['Tag', 'Name', 'Value', 'Description'])
    return output_df

# Function to split the FIX message into individual orders
def split_fix_orders(fix_message, user_separator=None):
    separator = user_separator if user_separator else '\x01'
    orders = fix_message.split("8=FIX")  # Splitting by '8=FIX' to identify separate orders
    return [("8=FIX" + order).strip() for order in orders if order]

# Function to create the summary table for all orders
def create_summary_table(decoded_orders):
    summary_data = []
    for order in decoded_orders:
        order_dict = {row['Tag']: row['Value'] for _, row in order.iterrows()}
        order_id = order_dict.get('11', 'Unknown')
        broker_id = order_dict.get('56', 'Unknown')
        client_id = order_dict.get('49', 'Unknown')
        symbol = order_dict.get('55', 'Unknown')
        qty = order_dict.get('38', 'Unknown')
        side = 'Buy' if order_dict.get('54', '') == '1' else 'Sell'
        ord_type = 'Market' if order_dict.get('40', '') == '1' else 'Limit'
        executed = 'Not Executed' if '39' not in order_dict else 'Executed'
        
        summary_data.append([order_id, broker_id, client_id, symbol, qty, side, ord_type, executed])
    
    summary_df = pd.DataFrame(summary_data, columns=['Order ID', 'Broker ID', 'Client ID', 'Stock/Security', 'Quantity', 'Buy/Sell', 'Order Type', 'Executed'])
    return summary_df

# Streamlit app
st.title("FIX Message Creator and Interpreter")

# Ensure state persists using st.session_state
if "fix_message_input" not in st.session_state:
    st.session_state.fix_message_input = ""
if "decoded_orders" not in st.session_state:
    st.session_state.decoded_orders = []
if "summary_df" not in st.session_state:
    st.session_state.summary_df = pd.DataFrame()

option = st.sidebar.selectbox("Choose an option", ("Create FIX Message", "Interpret FIX Message"))

if option == "Create FIX Message":
    st.header("Create FIX Message")
    
    # Input fields with descriptions and placeholder values
    order_id = st.text_input("Order ID", value="12345", help="A unique ID for the client order (Tag 11).")
    client_id = st.text_input("Client ID", value="CLIENT1", help="The sender's unique identifier (Tag 49).")
    broker_id = st.text_input("Broker ID", value="BROKER1", help="The receiver's unique identifier (Tag 56).")
    seq_num = st.number_input("Message Sequence Number", min_value=1, value=1, help="Sequence number of the message, which ensures that the messages are processed in the correct order.(Tag 34).")
    symbol = st.text_input("Symbol", value="AAPL", help="The security identifier (Tag 55).")
    side = st.selectbox("Side", options=["1 (Buy)", "2 (Sell)"], help="Indicates whether the order is to buy or sell (Tag 54).")
    qty = st.number_input("Quantity", min_value=1, value=1, help="Quantity of the order (Tag 38).")
    price = st.number_input("Price (leave blank for market order)", min_value=0.0, value=0.0, format="%.2f", help="Limit price (Tag 44).")

    if price <= 0:
        price = None  # Market order if price is not provided

    if st.button("Create FIX Message"):
        fix_message = create_fix_message(order_id, client_id, broker_id, str(seq_num), symbol, side[0], str(qty), price)
        display_message = fix_message.replace('\x01', '|')  # Replace SOH with '|'
        st.text_area("Generated FIX Message", value=display_message, height=200)

if option == "Interpret FIX Message":
    st.header("Interpret FIX Message")
    separator_input = st.text_input("Enter custom separator (if any)", help="Leave blank to auto-detect or use default separators ('^A' or SOH).")
    fix_message_input = st.text_area("Paste your FIX message here:", value=st.session_state.fix_message_input)

    if st.button("Interpret Message"):
        # Store the input to session state to persist it
        st.session_state.fix_message_input = fix_message_input
        
        # Split the FIX message into multiple orders
        fix_orders = split_fix_orders(fix_message_input, separator_input)
        
        # Decode each order into a DataFrame
        st.session_state.decoded_orders = [decode_fix_order(order, separator_input) for order in fix_orders]
        
        if st.session_state.decoded_orders:
            # Create the summary table and store in session state
            st.session_state.summary_df = create_summary_table(st.session_state.decoded_orders)
        else:
            st.warning("Could not decode the FIX message. Please check the format.")
    
    # Step 1: Show the summary table for all orders
    if not st.session_state.summary_df.empty:
        st.subheader("Summary of Orders")
        st.write(st.session_state.summary_df)
        
        # Step 2: Create a dropdown to select individual orders by their Order ID
        order_ids = st.session_state.summary_df['Order ID'].tolist()
        selected_order_id = st.selectbox("Select an Order ID", order_ids)
        
        # Step 3: Display the detailed breakdown for the selected order
        for i, order in enumerate(st.session_state.decoded_orders):
            if st.session_state.summary_df.iloc[i]['Order ID'] == selected_order_id:
                st.subheader(f"Details for Order ID: {selected_order_id}")
                st.write(order)
                break
