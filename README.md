# PaySolution Payment Provider for Odoo 18.0

A comprehensive payment Provider integration module for Pay Solution, supporting secure online payments for Thailand and Southeast Asia markets.

## 🌟 Features

### Payment Methods Support

- **Credit/Debit Cards**: Visa, MasterCard, JCB, UnionPay, American Express
- **QR Payments**: Mobile app scan-to-pay functionality  
- **Internet Banking**: Direct bank transfers from all major banks
- **E-Wallets**: PayPal , TrueMoney Wallet, Alipay, WeChat Pay

### Security & Compliance

- **PCI DSS v4.0.1 Compliant**: Full compliance with latest payment security standards
- **Secure Redirection**: No sensitive card data stored in Odoo
- **Webhook Verification**: Secure transaction status updates
- **Encrypted Communication**: All API calls use HTTPS/TLS 1.2+

### Technical Features

- **Multi-Currency Support**: THB, USD, JPY, SGD, HKD, EUR, GBP, AUD, CHF
- **Multi-Language**: Thai, English and Japanese support
- **Real-time Notifications**: Webhook integration for instant payment updates
- **Comprehensive Logging**: Full transaction audit trail

## 📋 Requirements

- **Odoo**: Version 18.0
- **PaySolutions Account**: Merchant account from https://paysolutions.asia/
- **SSL Certificate**: Required for webhook endpoints (HTTPS)

## 🚀 Installation

1. Download the module to your Odoo addons directory
2. Restart Odoo to recognize the new module
3. Go to Apps menu, search for "Pay Solutions"
4. Click Install

## ⚙️ Configuration

### 1. PaySolution Account Setup

1. Register for a PaySolution merchant account at: https://register.paysolutions.asia
2. Wait for account approval (7-15 business days)
3. Login to merchant control panel: https://controls.paysolutions.asia
4. Navigate to: Merchant Settings > Merchant Details
5. Note down your credentials:
   - Merchant ID (8 digits)
   - API Key
   - Secret Key

### 2. Odoo Configuration

1. **Navigate to Payment Providers**:
   
   - Go to Website > Configuration > Payment Providers
   - Find and select "Pay Solution"

2. **Configure Credentials**:
   
   - Enter your Merchant ID, API Key, and Secret Key

3. **Configure Webhooks**:
   
   - Copy the Post Back URL and Return URL from Odoo configuration
   - Add this URL to your Pay Solution merchant panel (Merchant Settings > Return Parameter)
   - Set PostBack Method to POST

## Support

- **Documentation**: See module description page or Pay Solutions Integration Documentation.pdf
- **PaySolutions API Docs**: https://api-docs.paysolutions.asia/
- **Technical Support**: Contact PaySolutions merchant support
- **Contact PaySolution Support Email**: support@paysolutions.asia
- Review Odoo logs for detailed error messages

## Author

**Kotchasaan Technology Invention Co., Ltd.**

## License

This module is licensed under LGPL-3.
