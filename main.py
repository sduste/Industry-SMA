import yfinance as yf
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import io
import os

from dotenv import load_dotenv
load_dotenv()

# Function to read tickers and industries from text file
def read_tickers_from_file(file_path):
    tickers = []
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line:
                ticker, industry = line.split(',')
                tickers.append((ticker.strip(), industry.strip())) # Store as tuple (ticker, industry)
    return tickers

# Calculate the Simple Moving Average (SMA)
def calculate_sma(stock_data, window):
    return stock_data.rolling(window=window).mean()

# Calculate the daily percentage of stocks where SMA 50 > SMA 200 for each industry
def calculate_daily_percentage(tickers, start_date, end_date):
    industries = set([industry for _, industry in tickers])
    daily_percentages = {industry: pd.DataFrame(columns=['Percentages']) for industry in industries}

    industry_tickers = {industry: [ticker for ticker, ind in tickers if ind == industry] for industry in industries}
    
    for industry, tickers in industry_tickers.items():
        combined_data = pd.DataFrame()
        print(f"Processing industry: {industry}")
        
        for ticker in tickers:
            print(f"Processing ticker: {ticker}")
            try:
                # Download stock data
                stock_data = yf.download(ticker, start=start_date, end=end_date)
                if stock_data.empty:
                    print(f"No data found for {ticker}.")
                    continue

                # Calculate SMAs
                stock_data['SMA50'] = calculate_sma(stock_data['Close'], 50)
                stock_data['SMA200'] = calculate_sma(stock_data['Close'], 200)

                # Determine where SMA50 > SMA200
                stock_data['SMA50_GT_SMA200'] = stock_data['SMA50'] > stock_data['SMA200']

                combined_data[ticker] = stock_data['SMA50_GT_SMA200']

                # Debugging output
                print(f"First few rows of SMA data for {ticker}:")
                print(stock_data[['SMA50', 'SMA200', 'SMA50_GT_SMA200']].head())

            except Exception as e:
                print(f"Error processing ticker {ticker}: {e}")
                continue

        if not combined_data.empty:
            combined_data.fillna(False, inplace=True)

            # Aggregate daily percentages
            for date in combined_data.index:
                sma50_gt_sma200_count = combined_data.loc[date].sum()
                total_tickers = len(tickers)
                percentage = (sma50_gt_sma200_count / total_tickers) * 100
                daily_percentages[industry].loc[date, 'Percentages'] = percentage
                print(f"Processed date: {date}, Industry: {industry}, Tickers above SMA: {sma50_gt_sma200_count}, Total Tickers: {total_tickers}, Percentage: {percentage:.2f}%")

    return daily_percentages

# Send email with the attached analysis
def send_email(subject, body, attachments):
    # Email credentials
    from_email = os.getenv('EMAIL')
    to_email = os.getenv('RECIPIENT_EMAIL')
    password = os.getenv('PASSWORD')

    # Set up the email server and login
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(from_email, password)

    # Create the email
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    # Adding attachments
    for filename, filecontent in attachments.items():
        part = MIMEBase('application', 'octet-stream')
        part.set_payload(filecontent)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition', f'attachment; filename={filename}')
        msg.attach(part)

    # Send the email
    server.send_message(msg)
    server.quit()

# Main function to execute the script
def main():
    file_path = 'tickers.txt'
    tickers = read_tickers_from_file(file_path)

    end_date = datetime.today()
    start_date = end_date - timedelta(days=5 * 365)

    daily_percentages = calculate_daily_percentage(tickers, start_date, end_date)

    attachments = {}
    for industry, df in daily_percentages.items():
        # Plotting the results
        plt.figure(figsize=(12, 6))
        plt.plot(df.index, df['Percentages'], label='SMA50 > SMA200')
        plt.xlabel('Date')
        plt.ylabel('Percentage of Stocks')
        plt.title(f'Daily Percentage of {industry} Stocks where SMA 50 > SMA 200 (Past 5 Years)')
        plt.legend()
        plt.grid(True)

        # Save the plot to a BytesIO object
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        buf.seek(0)
        attachments[f"{industry}_SMA_analysis.png"] = buf.read()
        buf.close()
        plt.close()

        # Logging for debugging
        print(f"Plot for {industry} saved and attached.")

    # Email subject and body
    subject = "Daily Industry SMA Analysis"
    body = "Please find attached the SMA analysis for different industries"

    # Send the email
    send_email(subject, body, attachments)
    print("Email sent with attachments.")

if __name__ == "__main__":
    main()
