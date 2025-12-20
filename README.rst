Rebalance
=========

|Build status| |Coverage| |Code Factor| |Docs| 

A calculator which tells you how to split your investment amongst your portfolio's assets based on your target asset allocation.

To use it, install the package and run the provided ``main.py`` driver file as described below.


.. raw:: html

        <div class="ui container">

        <h2 class="ui dividing header">Installation</h2>

                <div class="ui text container">
.. raw:: html

                    <h3 class="ui header">Clone the repository:</h3>

.. code-block:: bash

    git clone https://github.com/siavashadpey/rebalance.git

.. raw:: html

                    <h3 class="ui header">Install the package:</h3>

.. code-block:: bash

    cd rebalance
    pip3 install .

.. raw:: html

            	</div>
        </div>


        <div class="ui container">

        <h2 class="ui dividing header">Example</h2>


                    <h3 class="ui header">Create a YAML config:</h3>

                    <p>The driver reads a YAML config that points to a CSV export of your positions and supplies cash plus target allocations.</p>

.. code-block:: yaml

    positions_csv: Portfolio_Positions_Dec-19-2025.csv
    target_asset_alloc:
      FTEC: 30
      FNCMX: 25
      SOXX: 25
      FITLX: 20
    cash_amounts: [3000.0]
    cash_currency: ["USD"]

.. raw:: html

                    <p>The CSV needs "Symbol" and "Quantity" columns. Rows below the main table are ignored once the Symbol is empty, and the Symbol "SPAXX**" is always discarded.</p>

.. raw:: html

                    <h3 class="ui header">Run the driver:</h3>

.. code-block:: bash

    cd rebalance
    python main.py portfolio.yaml

.. raw:: html

                    <p>You should see something similar to this (the actual values might differ due to changes in prices and exchange rates).</p>

.. code-block:: bash

      Ticker      Ask     Quantity      Amount    Currency     Old allocation   New allocation     Target allocation
                           to buy         ($)                      (%)              (%)                 (%)
     ---------------------------------------------------------------------------------------------------------------
       XBB.TO    33.43       30         1002.90      CAD          17.52            19.99               20.00
       XIC.TO    24.27       27          655.29      CAD          22.61            20.01               20.00
         ITOT    69.38       10          693.80      USD          43.93            35.88               36.00
         IEFA    57.65       20         1153.00      USD           9.13            19.88               20.00
         IEMG    49.14        0            0.00      USD           6.81             4.24                4.00

     Largest discrepancy between the new and the target asset allocation is 0.24 %.

     Before making the above purchases, the following currency conversion is required:
         1072.88 USD to 1458.19 CAD at a rate of 1.3591.

     Remaining cash:
         80.32 USD.
         0.00 CAD.
	
.. raw:: html

        </div>



.. |Build Status| image:: https://travis-ci.org/siavashadpey/rebalance.svg?branch=master
	:target: https://travis-ci.org/siavashadpey/rebalance.svg?branch=master
	
.. |Coverage| image:: https://coveralls.io/repos/github/siavashadpey/rebalance/badge.svg?branch=master
	:target: https://coveralls.io/repos/github/siavashadpey/rebalance/badge.svg?branch=master

.. |Code Factor| image:: https://www.codefactor.io/repository/github/siavashadpey/rebalance/badge
   :target: https://www.codefactor.io/repository/github/siavashadpey/rebalance

.. |Docs| image:: https://readthedocs.org/projects/rebalance/badge/?version=latest
	:target: https://rebalance.readthedocs.io/en/latest/?badge=latest
	:alt: Documentation Status
