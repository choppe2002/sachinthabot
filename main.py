import csv
import datetime
import random
import string
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler, JobQueue, Job

import pandas as pd

# Replace 'YOUR_BOT_TOKEN' with your actual bot token
TOKEN = '6460034160:AAG33ucJQmBQ8l5yYMaNo7iMbWd5guXO0Qw'

# Owner's user ID
OWNER_USER_ID = 1925491630  # Replace with your actual user ID

# Dictionary to store generated keys and their details
keys_data = {}

# Load aviator game data
aviator_game_data = pd.read_csv('aviator_game_data.csv')

# Conversation states
START, ENTER_KEY, REMOVE_KEY, PREDICT_MULTIPLIER, PREDICT_MULTIPLIER_ON_DEMAND = range(5)

# Function to generate a random key of a specified length
def generate_key(length=30):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(length))

# Function to generate a multiplier with special probabilities
def generate_multiplier():
    # Generate a random number between 1 and 30
    generated_value = random.uniform(1, 30)

    # Introduce lower probability for values exceeding 5
    if generated_value > 5:
        if random.random() < 0.9:  # 20% probability
            generated_value = random.uniform(1.2, 5)

    # Reduce likelihood for values surpassing 15
    if generated_value > 15:
        if random.random() < 0.1:  # 10% probability
            generated_value = random.uniform(1.2, 15)

    return generated_value

# Function to handle the /generatekey command
def generate_key_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if user_id != OWNER_USER_ID:
        update.message.reply_text("You are not authorized to use this command.")
        return ConversationHandler.END

    update.message.reply_text("Please provide the user ID for whom you want to generate the key and the key duration (e.g., 5m, 1h, 1d, 7d, 30d).")

    return ENTER_KEY

# Function to handle incoming messages during key generation
def enter_key(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    provided_data = update.message.text.split()

    if len(provided_data) != 2:
        update.message.reply_text("Invalid input. Please provide the user ID and key duration.")
        return ENTER_KEY

    try:
        provided_user_id = int(provided_data[0])
        key_duration = int(provided_data[1][:-1])
        duration_unit = provided_data[1][-1]
    except ValueError:
        update.message.reply_text("Invalid input. Please provide valid user ID and key duration.")
        return ENTER_KEY

    key = generate_key()
    expiration_time = calculate_expiration_time(key_duration, duration_unit)

    keys_data[key] = {'user_id': provided_user_id, 'expiration_time': expiration_time}
    save_keys_to_csv()

    update.message.reply_text(f"Key generated successfully! Key: {key}, User ID: {provided_user_id}")

    return ConversationHandler.END

# Function to calculate expiration time based on provided duration and unit
def calculate_expiration_time(duration, unit):
    unit_multipliers = {'m': 1, 'h': 60, 'd': 1440}
    multiplier = unit_multipliers.get(unit, 1)
    return datetime.datetime.now() + datetime.timedelta(minutes=duration * multiplier)

# Function to handle the /start command
def start(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id

    if user_id in [data['user_id'] for data in keys_data.values()]:
        update.message.reply_text("You've already been granted access.")
        return ConversationHandler.END
    else:
        update.message.reply_text("Welcome! Please enter the key to access the bot.", reply_markup=ReplyKeyboardRemove())
        return ENTER_KEY

# Function to handle incoming messages and check for valid keys
def check_key(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_text = update.message.text

    # Remove expired keys
    remove_expired_keys(context.job)

    if user_text and user_text.isdigit():
        # Handle the case where the user sends a number without a command
        handle_multiplier_prediction(update, context)
        return

    if user_id in [data['user_id'] for data in keys_data.values()]:
        update.message.reply_text("You've already been granted access.")
        return

    if user_text in keys_data:
        key_info = keys_data[user_text]
        if key_info['user_id'] == user_id and key_info['expiration_time'] > datetime.datetime.now():
            update.message.reply_text("Access granted!", reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text("Invalid key or key has expired.")
    else:
        update.message.reply_text("Invalid key. Please purchase a key to continue.")

# Function to save keys to a CSV file
def save_keys_to_csv():
    with open('keys_data.csv', 'w', newline='') as csvfile:
        fieldnames = ['key', 'user_id', 'expiration_time']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for key, data in keys_data.items():
            writer.writerow({'key': key, 'user_id': data['user_id'], 'expiration_time': data['expiration_time']})

# Function to load keys from a CSV file (if any)
def load_keys_from_csv():
    try:
        with open('keys_data.csv', 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                keys_data[row['key']] = {'user_id': int(row['user_id']),
                                          'expiration_time': datetime.datetime.strptime(row['expiration_time'],
                                                                                        '%Y-%m-%d %H:%M:%S.%f')}
    except FileNotFoundError:
        pass

# Function to remove expired keys from the system
def remove_expired_keys(context: CallbackContext = None, job: Job = None) -> None:
    current_time = datetime.datetime.now()
    expired_keys = [key for key, data in keys_data.items() if data['expiration_time'] < current_time]

    for key in expired_keys:
        del keys_data[key]

    if expired_keys:
        save_keys_to_csv()

# Function to handle the /removekey command
def remove_key_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if user_id != OWNER_USER_ID:
        update.message.reply_text("You are not authorized to use this command.")
        return

    update.message.reply_text("Please provide the user ID for whom you want to remove the key.")

    return REMOVE_KEY

# Function to handle incoming messages during key removal
def remove_key(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    provided_user_id = int(update.message.text)

    keys_to_remove = [key for key, data in keys_data.items() if data['user_id'] == provided_user_id]
    for key in keys_to_remove:
        del keys_data[key]

    save_keys_to_csv()

    if keys_to_remove:
        update.message.reply_text("User's key has been revoked.")
    else:
        update.message.reply_text("No keys found for the specified user.")

    return ConversationHandler.END

# Function to handle the /predictmultiplier command
def predict_multiplier(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id

    if user_id not in [data['user_id'] for data in keys_data.values()]:
        update.message.reply_text("You need to have access to the bot to predict the next multiplier.")
        return ConversationHandler.END

    update.message.reply_text("Please enter the actual multiplier from the previous aviator game.")

    return PREDICT_MULTIPLIER

# Function to handle incoming messages during multiplier prediction
def handle_multiplier_prediction(update: Update, context: CallbackContext) -> int:
    user_id = update.message.from_user.id
    user_text = update.message.text

    try:
        actual_multiplier = float(user_text)
    except ValueError:
        update.message.reply_text("Invalid input. Please provide a valid multiplier.")
        return PREDICT_MULTIPLIER

    # Search for the provided multiplier in the aviator game data
    matching_row = aviator_game_data[aviator_game_data['multiplier'] == actual_multiplier]

    if not matching_row.empty:
        # Get the index of the matching row
        matching_index = matching_row.index[0]

        # Select the next multiplier value in the dataset
        selected_index = matching_index + 1
        if selected_index < len(aviator_game_data):
            selected_value = aviator_game_data.at[selected_index, 'multiplier']

            generated_value = generate_multiplier()

            if actual_multiplier > 5:
                # Send a warning message if the previous round value is greater than 5
                warning_message = "⚠️ Warning: The previous round value was greater than 5. Be cautious, the next round may crash at 1.0 or below."
                update.message.reply_text(warning_message)

            if actual_multiplier == selected_value:
                update.message.reply_text("Prediction correct! You matched the actual multiplier.")
            else:
                # Regenerate a random value within the range of selected and generated values
                regenerated_value = random.uniform(min(selected_value, generated_value), max(selected_value, generated_value))

                output_message = (
                    f"Actual multiplier: {actual_multiplier}\n"
                    f"Selected value: {selected_value}\n"
                    f"Predicted value: {generated_value}\n"
                    f"Take Winnings: {regenerated_value}"
                )

                update.message.reply_text(output_message)

            return ConversationHandler.END
        else:
            update.message.reply_text("No next value available in the aviator game data.")
            return PREDICT_MULTIPLIER
    else:
        update.message.reply_text("Provided multiplier not found in the aviator game data. Please provide a valid multiplier.")
        return PREDICT_MULTIPLIER

# Function to assist users in predicting the next multiplier on demand
def predict_multiplier_on_demand(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id

    if user_id not in [data['user_id'] for data in keys_data.values()]:
        update.message.reply_text("You need to have access to the bot to predict the next multiplier.")
        return

    try:
        actual_multiplier = float(update.message.text)
    except ValueError:
        update.message.reply_text("Invalid input. Please provide a valid multiplier.")
        return

    # Search for the provided multiplier in the aviator game data
    matching_row = aviator_game_data[aviator_game_data['multiplier'] == actual_multiplier]

    if not matching_row.empty:
        # Get the index of the matching row
        matching_index = matching_row.index[0]

        # Select the next multiplier value in the dataset
        selected_value = aviator_game_data.at[matching_index + 1, 'multiplier']

        generated_value = generate_multiplier()

        if actual_multiplier == selected_value:
            update.message.reply_text("Prediction correct! You matched the actual multiplier.")
        else:
            # Regenerate a random value within the range of selected and generated values
            regenerated_value = random.uniform(min(selected_value, generated_value), max(selected_value, generated_value))

            output_message = (
                    f"Actual multiplier: {actual_multiplier}\n"
                    f"Selected value: {selected_value}\n"
                    f"Predicted value: {generated_value}\n"
                    f"Take Winnings: {regenerated_value}"
                )

            update.message.reply_text(output_message)
    else:
        update.message.reply_text("Provided multiplier not found in the aviator game data. Please provide a valid multiplier.")

# ...

# Function to handle incoming messages and check for valid keys
def check_key(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_text = update.message.text

    # Remove expired keys
    remove_expired_keys(context.job)

    if user_text and user_text.isdigit():
        # Handle the case where the user sends a number without a command
        handle_multiplier_prediction(update, context)
        return

    if user_id in [data['user_id'] for data in keys_data.values()]:
        update.message.reply_text("You've already been granted access.")
        return

    if user_text in keys_data:
        key_info = keys_data[user_text]
        if key_info['user_id'] == user_id and key_info['expiration_time'] > datetime.datetime.now():
            update.message.reply_text("Access granted!", reply_markup=ReplyKeyboardRemove())
        else:
            update.message.reply_text("Invalid key or key has expired.")
    else:
        update.message.reply_text("Invalid key. Please purchase a key to continue.")

# ...

def main():
    updater = Updater(token=TOKEN, use_context=True)
    dispatcher = updater.dispatcher
    job_queue = updater.job_queue

    load_keys_from_csv()

    # Conversation handlers
    conv_handler_generatekey = ConversationHandler(
        entry_points=[CommandHandler('generatekey', generate_key_command)],
        states={
            ENTER_KEY: [MessageHandler(Filters.text & ~Filters.command, enter_key)],
        },
        fallbacks=[],
    )

    conv_handler_removekey = ConversationHandler(
        entry_points=[CommandHandler('removekey', remove_key_command)],
        states={
            REMOVE_KEY: [MessageHandler(Filters.text & ~Filters.command, remove_key)],
        },
        fallbacks=[],
    )

    conv_handler_predict_multiplier = ConversationHandler(
        entry_points=[CommandHandler('predictmultiplier', predict_multiplier)],
        states={
            PREDICT_MULTIPLIER: [MessageHandler(Filters.text & ~Filters.command, handle_multiplier_prediction)],
        },
        fallbacks=[],
    )

    # Add new conversation handler for predicting multiplier on demand
    conv_handler_predict_multiplier_on_demand = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, predict_multiplier_on_demand)],
        states={
            PREDICT_MULTIPLIER_ON_DEMAND: [MessageHandler(Filters.text & ~Filters.command, predict_multiplier_on_demand)],
        },
        fallbacks=[],
    )

    # Handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(conv_handler_generatekey)
    dispatcher.add_handler(conv_handler_removekey)
    dispatcher.add_handler(conv_handler_predict_multiplier)
    dispatcher.add_handler(conv_handler_predict_multiplier_on_demand)
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, check_key))

    # Schedule job to remove expired keys every 24 hours
    job_queue.run_repeating(remove_expired_keys, interval=300)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
