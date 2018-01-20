import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from print_t import *
import sys

# Default file location is not set to manual
file_location = r'ohlc_2017-10-01_2017-10-31.csv'

# THE DIFFERENT PERIODS OF SMAS WE ARE GOING TO CHECK AGAINST
smas = [5, 10, 20, 50, 100, 200]
min_percent = 1
max_percent = 9

# A DICTIONARY TO STORE THE RESULTS OF EACH SIMULATION
results = {}


def print_help():
	"""Help message"""
	print("""
manual usage: investabit_1.py -m
PROMPTS USER FOR MANUAL INPUTS

PROGRAM RUNS WITH DEFAULT VALUES IF NO ARGUMENTS

		""")


def get_args():
	"""Getting arguments, not needed but has a manual mode"""
	global file_location, smas, min_percent, max_percent
	if len(sys.argv) == 2:
		if sys.argv[1] == '-d':
			print_t('RUNNING WITH DEFAULT VALUES', 'PASS')
		elif sys.argv[1] == '-m':
			file_location = input('ENTER FILE LOCATION: ')
			file_location = file_location.replace('"', '')
			smas = input('ENTER SMAS SEPARATED BY COMMA: ')
			smas = smas.split(', ')
			smas = list(map(int, smas))
			min_percent = int(input('ENTER MINIMUM PERCENT: '))
			max_percent = int(input('ENTER MAXIMUM PERCENT: '))
		elif sys.argv[1] == '-h':
			print_help()
			exit()


def load_data(file_name):
	"""Makes Pandas dataframes for each of the currencies and returns them
	and resets the indexes"""
	df = pd.read_csv(file_name)
	eth_df = df[df.symbol.str.contains('ETHUSD') == True]
	btc_df = df[df.symbol.str.contains('BTCUSD') == True]
	xrp_df = df[df.symbol.str.contains('XRPUSD') == True]
	eth_df.reset_index(inplace=True, drop=True)
	btc_df.reset_index(inplace=True, drop=True)
	xrp_df.reset_index(inplace=True, drop=True)
	return eth_df, btc_df, xrp_df


def get_moving_averages(dataframe):
	"""Add some columns that are useful, moving averages, rsi, etc
	We are going to try a few different crossover strategies
	We are also going to add holdings and fiat columns to track account"""
	for sma in smas:
		frame_name = str(sma) + '_sma'
		dataframe[frame_name] = dataframe['weighted_price'].rolling(window=int(sma)).mean()
	dataframe['holdings'] = np.nan
	dataframe['fiat'] = np.nan
	dataframe['sell_price'] = np.nan
	dataframe.ix[0, 'fiat'] = 33333.33
	dataframe.ix[0, 'holdings'] = 0
	return dataframe


def auto_trade(dataframe, short_sma_period, long_sma_period, percentage):
	"""This is going to do a simple moving average crossover strategy"""
	short_sma = str(short_sma_period) + '_sma'
	long_sma = str(long_sma_period) + '_sma'
	previous_crossover = True
	for index, row in dataframe.iterrows():
		next_index = index + 1
		# FIRST WE WILL CHECK IF WE HAVE SOMETHING TO SELL
		if dataframe.iloc[index]['sell_price'] > 0.0:
			if dataframe.iloc[index]['weighted_price'] >= dataframe.iloc[index]['sell_price']:
				new_fiat = dataframe.iloc[index]['sell_price'] * dataframe.iloc[index]['holdings']\
						   + dataframe.iloc[index]['fiat']
				print_t(str(dataframe.iloc[index]['timestamp']) + ' [-] SELLING ' +
						str(dataframe.iloc[index]['holdings']) + ' @ ' + str(dataframe.iloc[index]['sell_price']) +
						' FOR ' + str(new_fiat), 'pass')
				dataframe.set_value(next_index, 'holdings', 0)
				dataframe.set_value(next_index, 'fiat', new_fiat)
				dataframe.set_value(next_index, 'sell_price', np.nan)
			else:
				dataframe.set_value(next_index, 'holdings', dataframe.iloc[index]['holdings'])
				dataframe.set_value(next_index, 'fiat', dataframe.iloc[index]['fiat'])
				dataframe.set_value(next_index, 'sell_price', dataframe.iloc[index]['sell_price'])

		# THIS IS THE BUYING SECTION
		elif index != 0:
			if pd.isnull(row[long_sma]):
				# IF LONG SMA IS NAN JUST CARRY DOWN THE VALUES
				dataframe.set_value(next_index, 'holdings', dataframe.iloc[index]['holdings'])
				dataframe.set_value(next_index, 'fiat', dataframe.iloc[index]['fiat'])
				dataframe.set_value(next_index, 'sell_price', dataframe.iloc[index]['sell_price'])
			elif row[short_sma] <= row[long_sma]:
				# IF SHORT SMA IS LESS THAN  LONG SMA DO NOTHING AND CARRY DOWN VALUES
				dataframe.set_value(next_index, 'holdings', dataframe.iloc[index]['holdings'])
				dataframe.set_value(next_index, 'fiat', dataframe.iloc[index]['fiat'])
				dataframe.set_value(next_index, 'sell_price', dataframe.iloc[index]['sell_price'])
				previous_crossover = False
			elif row[short_sma] > row[long_sma]:
				# IF SHORT SMA IS GREATER THAN LONG SMA, POSSIBLY BUY
				if not previous_crossover:
					# THIS MEANS IT HAS JUST CROSSED OVER SO WE BUY
					previous_crossover = True
					new_holdings = dataframe.iloc[index]['fiat'] / dataframe.iloc[index]['weighted_price']
					new_fiat = 0
					sell_price = percentage * dataframe.iloc[index]['weighted_price']
					available_volume = dataframe.iloc[index]['volume']
					if new_holdings > available_volume:
						print_t('SHORTAGE OF VOLUME, BUYING LESSER AMOUNT', 'FAIL')
						print_t(str(dataframe.iloc[index]['timestamp']) + ' [+] BUYING ' + str(available_volume)
								+ ' @ ' + str(dataframe.iloc[index]['weighted_price'])
								+ ' TO SELL @ ' + str(sell_price), 'pass')
						remaining_fiat = dataframe.iloc[index]['fiat'] - \
										 (available_volume * dataframe.iloc[index]['weighted_price'])
						dataframe.set_value(next_index, 'holdings', available_volume)
						dataframe.set_value(next_index, 'sell_price', sell_price)
						dataframe.set_value(next_index, 'fiat', remaining_fiat)
					elif new_holdings <= available_volume:
						print_t(str(dataframe.iloc[index]['timestamp']) + ' [+] BUYING ' + str(new_holdings) + ' @ '
								+ str(dataframe.iloc[index]['weighted_price']) +
								' TO SELL @ ' + str(sell_price), 'pass')
						dataframe.set_value(next_index, 'holdings', new_holdings)
						dataframe.set_value(next_index, 'fiat', new_fiat)
						dataframe.set_value(next_index, 'sell_price', sell_price)
				elif previous_crossover:
					# THIS MEANS IT WAS ALREADY CROSSED OVER SO WE DON'T DO ANYTHING
					dataframe.set_value(next_index, 'holdings', dataframe.iloc[index]['holdings'])
					dataframe.set_value(next_index, 'fiat', dataframe.iloc[index]['fiat'])
					dataframe.set_value(next_index, 'sell_price', dataframe.iloc[index]['sell_price'])
		elif index == 0:
			# carry down for first row
			dataframe.set_value(next_index, 'holdings', dataframe.iloc[index]['holdings'])
			dataframe.set_value(next_index, 'fiat', dataframe.iloc[index]['fiat'])
			dataframe.set_value(next_index, 'sell_price', dataframe.iloc[index]['sell_price'])

	# Finally sell any remaining crypto to measure performance
	# Real world you wouldn't sell but it would wait until it's sell price was reached
	df_length = dataframe.shape[0] - 1
	if dataframe.iloc[df_length]['holdings'] != 0.0:
		new_fiat = (dataframe.iloc[df_length]['holdings'] * dataframe.iloc[(df_length - 1)]['weighted_price']) \
				   + dataframe.iloc[(df_length)]['fiat']
		dataframe.set_value(df_length, 'holdings', 0)
		dataframe.set_value(df_length, 'fiat', new_fiat)
		print_t('UNCLOSED CRYPTO AT END. ASSUMING SELLING AT MARKET PRICE.', 'fail')

	final_value = dataframe.iloc[df_length]['fiat']
	if final_value > 33333.33:
		status = 'hard pass'
	else:
		status = 'hard fail'
	print_t('FINAL PORTFOLIO VALUE: ' + str(final_value), status)

	# Adding a running account value column
	dataframe['acount_value'] = np.nan
	for index, row in dataframe.iterrows():
		fiat = dataframe.iloc[index]['fiat']
		holdings = dataframe.iloc[index]['holdings']
		price = dataframe.iloc[index]['weighted_price']
		account_value = fiat + (holdings * price)
		dataframe.set_value(index, 'account_value', account_value)

	return final_value


def evaluate():
	"""We are going to run through a bunch of combinations of Simple Moving Averages and percentages"""
	for small_sma in smas:
		for large_sma in smas:
			if small_sma < large_sma:
				for percentage in range(min_percent, max_percent + 1):
					percentage2 = 1 + percentage / 100
					eth_df, btc_df, xrp_df = load_data(file_location)
					print_t('CHECKING WITH SMALL SMA @ ' + str(small_sma) + ' AND LARGE SMA @ ' + str(
						large_sma) + ' @ ' + str(percentage) + '%', 'warn')
					print_t('CHECKING ETH', 'WARN')
					get_moving_averages(eth_df)
					eth_final_value = auto_trade(eth_df, small_sma, large_sma, percentage2)
					print_t('CHECKING BTC', 'WARN')
					get_moving_averages(btc_df)
					btc_final_value = auto_trade(btc_df, small_sma, large_sma, percentage2)
					print_t('CHECKING XRP', 'WARN')
					get_moving_averages(xrp_df)
					xrp_final_value = auto_trade(xrp_df, small_sma, large_sma, percentage2)
					total_value = eth_final_value + btc_final_value + xrp_final_value
					if total_value > 100000.00:
						status = 'hard pass'
					else:
						status = 'hard fail'
					print_t('OVERALL PORTFOLIO VALUE: ' + str(total_value), status)
					results[total_value] = (small_sma, large_sma, percentage2)
	# Final values were stored as keys in a dictionary so we just get the max
	best_strategy = max(results.keys())
	print_t('BEST STRATEGY IS ' + str(results[best_strategy]) + ' WITH A FINAL VALUE OF ' + str(best_strategy),
			'hard pass')
	# Then we rerun it and plot the results
	plot_best_strategy(results[best_strategy][0], results[best_strategy][1], results[best_strategy][2])


def plot_best_strategy(small_sma, large_sma, percentage):
	"""We are going to take the best strategy and rerun it and plot the results"""
	print_t('RERUNNING BEST STRATEGY...', 'WARN')
	eth_df, btc_df, xrp_df = load_data(file_location)
	get_moving_averages(eth_df)
	get_moving_averages(btc_df)
	get_moving_averages(xrp_df)
	eth_final_value = auto_trade(eth_df, small_sma, large_sma, percentage)
	btc_final_value = auto_trade(btc_df, small_sma, large_sma, percentage)
	xrp_final_value = auto_trade(xrp_df, small_sma, large_sma, percentage)
	total_value = eth_final_value + btc_final_value + xrp_final_value
	print_t('OVERALL PORTFOLIO VALUE: ' + str(total_value), 'hard pass')
	profit_df = pd.DataFrame(columns=['ETH', 'BTC', 'XRP'])
	profit_df['ETH'] = eth_df['account_value']
	profit_df['BTC'] = btc_df['account_value']
	profit_df['XRP'] = xrp_df['account_value']
	profit_df.plot()
	print_t('BEST STRATEGY: SMALL SMA OF ' + str(small_sma) + ' LARGE SMA OF ' + str(large_sma) + ' WITH PERCENTAGE @ '
			+ str(percentage), 'hard pass')
	plt.show()


if __name__ == '__main__':
	start_logging('investabit_1.log')
	get_args()
	evaluate()
	quit_check = input('PRESS ENTER TO QUIT...')
