**3Commas FTX Triggers**

This collection of scripts creates a set of trading bots on [3Commas.io](https://3commas.io/?c=tc161202) based on available perpetual futures on [FTX.com](https://ftx.com/#a=10167807), and automatically provides triggers for those bots to start deals.

You'll need connected accounts on both [3Commas.io](https://3commas.io/?c=tc161202) and on [FTX.com](https://ftx.com/#a=10167807) for this to work. For more on how to connect 3Commas to FTX, checkout [this guide](https://onepercent.blog/2021/04/25/connect-your-3commas-account-to-ftx-com/).

To use:

1. Download/copy the files to a folder on your machine and install any dependancies. These will most likely be [ccxt](https://github.com/ccxt/ccxt) and [Py3CW](https://github.com/bogdanteodoru/py3cw).
2. Rename `example.config.py` to `config.py`, and edit the file to include your API keys and bot preferences.
3. Run the `Py3c_create.py` script to generate the 3Commas bots. This will also create a few tex files which include a list of trading pairs ignored if minimum size requirements aren't met, as well as a bot id list for both long and short bots.
4. Run the `Py3c_update.py` script and choose the **Enable bots** option.
5. Run the `Py3c_triggers.py` script to let the fun begin.  

More details on all the config settings, how the script works, and how to run continuously without leaving your computer on 24/7, will follow soon. 
