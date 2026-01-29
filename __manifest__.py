# -*- coding: utf-8 -*-
{
    'name': 'Pay Solutions Payment Provider',
    'version': '17.0.1.0.0',
    'category': 'Accounting/Payment Providers',
    'summary': 'Accept payments via PaySolutions: Cards, PromptPay, Internet Banking, E-Wallets & Installments for Thai market',
    'description': """
PaySolutions Payment Provider for Odoo 17
=========================================

Integrate PaySolutions - Thailand's leading payment gateway - with your Odoo eCommerce 
and Invoicing. Accept payments from Thai customers through their preferred payment methods.

Payment Methods Supported
-------------------------

**Credit & Debit Cards**

* Visa / MasterCard / JCB
* American Express
* China UnionPay

**QR Code Payments**

* PromptPay (Thai national QR standard)

**E-Wallets**

* TrueMoney Wallet
* Alipay
* WeChat Pay

**Internet Banking**

* Kasikorn Bank (KBank)
* Siam Commercial Bank (SCB)
* Krung Thai Bank (KTB)
* Bank of Ayudhya (Krungsri)
* Bangkok Bank (BBL)
* TMBThanachart Bank (TTB)

Key Features
------------

* Redirect-based secure payment flow
* Real-time webhook notifications
* Automatic invoice reconciliation
* Pending transaction monitoring with auto-cleanup
* Multi-currency support (THB, USD, EUR, GBP, JPY, SGD, HKD, AUD, CHF)
* 3 languages supported: Thai, English, and Japanese

Configuration
-------------

1. Go to Website > Configuration > Payment Providers
2. Select PaySolutions and click Configure
3. Enter credentials from PaySolutions merchant dashboard:

   * Merchant ID (8 digits)
   * API Key
   * Secret Key

4. Copy Webhook URL to PaySolutions dashboard
5. Activate the provider

Requirements
------------

* Odoo 17.0
* PaySolutions merchant account (https://paysolutions.asia/)
* SSL certificate (HTTPS) for webhook endpoints

Support
-------

* Documentation: See module description page or 
* Technical Support: Contact PaySolutions merchant support
    """,
    'author': "Kotchasaan Technology Invention Co.,Ltd.",
    'website': 'https://paysolutions.asia/',
    'depends': ['payment', 'account', 'sale'],
    'data': [
        'security/ir.model.access.csv',
        'data/payment_provider_data.xml',
        'data/cron.xml',
        'views/paysolutions_template_views.xml',
        'views/payment_transaction_views.xml',
    ],
    'images': [
        'static/description/icon.png',
        'static/description/images/main_screenshot.png'
    ],
    'post_init_hook': 'post_init_hook',
    'uninstall_hook': 'uninstall_hook',
    'installable': True,
    'auto_install': False,
    'application': True,
    'license': 'LGPL-3',
}