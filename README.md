# PaySolutions Payment Provider for Odoo 19.0

A comprehensive payment gateway integration for PaySolutions, Thailand's leading payment service provider. Accept PromptPay QR, credit cards, internet banking, and e-wallets with seamless Odoo integration.


## Table of Contents

- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [Changelog](#changelog)
- [Contributing](#contributing)
- [License](#license)
- [Support](#support)

---

## Features

### Payment Methods Support

- **PromptPay QR Code**: Thailand's national QR payment standard for instant bank transfers
- **Credit/Debit Cards**: Visa, MasterCard, JCB, UnionPay, American Express
- **Internet Banking**: SCB, Krungthai, Bangkok Bank, Kasikorn Bank, and other major Thai banks
- **E-Wallets**: TrueMoney Wallet, Alipay, WeChat Pay, PayPal
- **Installment Plans**: Credit card installment options with 0% interest available

### Security & Compliance

- **PCI DSS v4.0.1 Compliant**: Full compliance with the latest payment security standards
- **Secure Redirection**: No sensitive card data stored in Odoo
- **Webhook Verification**: Secure transaction status updates with signature validation
- **Encrypted Communication**: All API calls use HTTPS with TLS 1.2 or higher

### Technical Features

- **Multi-Currency Support**: THB, USD, JPY, SGD, HKD, EUR, GBP, AUD, CHF
- **Multi-Language Interface**: Thai, English, and Japanese
- **Real-time Webhook Integration**: Instant payment confirmation and status updates
- **Flexible Reconciliation**: Configurable automatic or manual invoice reconciliation
- **Automated Transaction Handling**: Scheduled job to detect and resolve pending transactions
- **Advanced Monitoring Tools**: 
  - Quick action buttons for bulk operations
  - Real-time payment status verification
  - Comprehensive transaction logs in Developer Mode
- **Test Mode Support**: Sandbox environment for development and testing
- **Comprehensive Logging**: Complete transaction audit trail with webhook payload inspection


## Requirements

### System Requirements

- **Odoo Version**: 19.0 (for other versions, see branches: [17.0](../../tree/17.0), [18.0](../../tree/18.0))
- **Python**: Version 3.10 or higher
- **PostgreSQL**: Version 12.0 or higher
- **SSL Certificate**: Required for production webhook endpoints (HTTPS)

### Odoo Module Dependencies

- `payment` - Payment Engine (automatically installed)
- `account` - Accounting module
- `sale` - Sales module

### PaySolutions Account Requirements

- Active merchant account from [PaySolutions](https://paysolutions.asia/)
- Business registration in Thailand or Southeast Asia
- Approved merchant status (approval time: 7-15 business days)


## Installation

### Method 1: Odoo.sh Installation (Recommended)

1. Visit the [PaySolutions module page](https://apps.odoo.com/apps/modules/19.0/payment_paysolutions/) on Odoo App Store
2. Click the "Deploy on Odoo.sh" button
3. Select your project and target branch
4. The module will be automatically deployed and installed

### Method 2: Manual Installation (Self-hosted)

#### Step 1: Download Module

Download the module ZIP file from Odoo App Store or GitHub releases.

#### Step 2: Extract to Addons Directory

```bash
cd /opt/odoo/custom/addons/
unzip payment_paysolutions-19.0.1.0.0.zip
```

#### Step 3: Set Permissions (Linux/Unix)

```bash
sudo chown -R odoo:odoo payment_paysolutions/
sudo chmod -R 755 payment_paysolutions/
```

#### Step 4: Restart Odoo Service

```bash
sudo systemctl restart odoo
```

#### Step 5: Update Apps List

1. Enable Developer Mode: Settings → Activate Developer Mode
2. Navigate to Apps menu
3. Click the menu icon (three dots) → Update Apps List
4. Click Update button

#### Step 6: Install Module

1. Search for "PaySolutions" in the Apps menu
2. Remove the "Apps" filter if the module is not visible
3. Click the Install button

**For detailed installation instructions**, refer to the [Installation Documentation](docs/INSTALLATION.md).

**Video Tutorial**: [Module Installation Guide](https://youtu.be/KCGAKbVT92k)


## Configuration

### Step 1: PaySolutions Account Setup

#### Register for Merchant Account

1. Complete registration at [PaySolutions Registration](https://register.paysolutions.asia)
2. Wait for account approval (7-15 business days)
3. Login to the [Merchant Control Panel](https://controls.paysolutions.asia)

#### Retrieve Credentials

1. Navigate to: Merchant Settings → Merchant Details
2. Record the following credentials:
   - Merchant ID (8-digit identifier)
   - API Key
   - Secret Key

### Step 2: Configure Payment Provider in Odoo

#### Access Payment Provider Configuration

1. Navigate to: Accounting → Configuration → Payment Providers
2. Locate and select "PaySolutions" from the list

#### Enter Credentials

Under the Credentials tab, configure the following:

- **Merchant ID**: Enter your 8-digit merchant identifier
- **API Key**: Enter the API key provided by PaySolutions
- **Secret Key**: Enter the secret key provided by PaySolutions

#### Configure Webhook and Return URLs

The system automatically generates the following URLs:

- **Webhook URL**: `https://your-domain.com/payment/paysolutions/webhook`
- **Return URL**: `https://your-domain.com/payment/paysolutions/return`

**To configure in PaySolutions Merchant Panel:**

1. Copy both URLs from Odoo configuration
2. Login to PaySolutions Merchant Control Panel
3. Navigate to: Merchant Settings → Return Parameter
4. Configure the following:
   - **Post Back URL**: Paste the Webhook URL
   - **Return URL**: Paste the Return URL
   - **PostBack Method**: Select "POST"
5. Save the configuration

### Step 3: Configure Payment Journal (Critical for Auto Reconciliation)

**Purpose**: Enable automatic invoice reconciliation when payments are confirmed.

**Default Behavior**: By default, PaySolutions uses an "Outstanding Receipts" account which requires manual reconciliation. To enable automatic reconciliation:

#### Configuration Steps

1. Navigate to: Accounting → Configuration → Journals
2. Open the **Bank** journal
3. Select the **Incoming Payments** tab
4. Locate the PaySolutions payment method
5. Click the **Setup** button (or edit the payment method directly)
6. Modify the **Outstanding Account** field:
   - **From**: `101403 Outstanding Receipts`
   - **To**: `101401 Bank` (or your designated bank account)
7. Save the configuration

#### Impact of Configuration

**Outstanding Receipts Account** (Default):
- Payments recorded to clearing account
- Invoice status: "In Payment"
- Requires manual reconciliation with bank statement

**Bank Account** (Recommended):
- Payments recorded directly to bank account
- Invoice status: Automatically updated to "Paid"
- No manual reconciliation required

For detailed explanation, see [Payment Account Configuration Guide](docs/AUTO_RECONCILIATION.md).

### Step 4: Activate Cron Job (Odoo 17.0 Only)

**IMPORTANT**: For Odoo version 17.0, the pending transaction checker cron job is disabled by default and must be manually activated.

**Note**: Odoo 18.0 and later versions have this cron job enabled by default.

#### Activation Procedure

1. Enable Developer Mode: Settings → Activate Developer Mode
2. Navigate to: Settings → Technical → Automation → Scheduled Actions
3. Search for: "PaySolutions: Check Pending Transactions"
4. Open the scheduled action record
5. Enable the "Active" checkbox
6. Verify the following settings:
   - **Interval Number**: 15
   - **Interval Unit**: Minutes
   - **Next Execution Date**: Should display an upcoming timestamp
7. Save the record


## Usage

### Customer Payment Flow

#### Standard Payment Process

1. **Checkout**: Customer selects PaySolutions as the payment method during checkout
2. **Redirect**: Customer is redirected to the PaySolutions secure payment page
3. **Payment Selection**: Customer selects preferred payment channel:
   - Scan PromptPay QR code using mobile banking app
   - Enter credit/debit card details
   - Select internet banking institution
   - Choose e-wallet option
4. **Transaction Completion**: Customer completes the payment transaction
5. **Return to Store**: Customer is automatically redirected back to Odoo
6. **Confirmation**: Order and invoice status automatically updated

#### Automatic Processing

When a payment is completed:

1. PaySolutions sends webhook notification to Odoo
2. Transaction status is updated based on gateway response
3. Invoice is automatically reconciled and marked as paid (if configured)
4. Customer receives confirmation email

### Payment Monitoring

#### Quick Actions (Payment Provider Level)

Access from: Accounting → Configuration → Payment Providers → PaySolutions

**Available Actions:**

- **PaySolutions Transactions** button: View comprehensive list of all transactions processed through PaySolutions
- **Check Status Now** button: Manually verify status of all pending transactions with PaySolutions gateway

#### Transaction Management (Individual Transaction Level)

Access from: Accounting → Customers → Payments or via PaySolutions Transactions list

**Available Tools:**

##### 1. Verify Payment Status (PaySolutions) Button

**Purpose**: Perform real-time status verification directly from PaySolutions gateway

**When to Use**:
- Transaction status appears to be stuck or outdated
- Immediate payment confirmation is required
- Investigating payment discrepancies or customer inquiries

**Functionality**:
- Sends real-time status inquiry to PaySolutions
- Updates transaction status based on gateway response
- Results displayed in Message Status tab

##### 2. Message Status Tab

**Purpose**: Quick overview of payment status and communication history

**Information Displayed**:
- Current payment status message (e.g., "Payment completed successfully")
- Status updates from webhook notifications
- Manual status check results
- Payment confirmation messages

**Use Case**: Suitable for regular users requiring quick status verification without technical details.

##### 3. PaySolutions Details Tab

**Purpose**: Detailed payment information received from PaySolutions gateway

**Information Included**:
- **orderNo**: PaySolutions order reference number
- **productdetail**: Description of the purchase
- **PaySolutions Card Type**: Payment method used (Visa, MasterCard, PromptPay, etc.)
- **status**: Payment status code (COMPLETED, PENDING, etc.)

**Use Case**: Essential for:
- Reconciliation with PaySolutions merchant reports
- Verifying payment method used by customer
- Troubleshooting payment issues with complete gateway data
- Customer support inquiries

##### 4. Logs Tab (Developer Mode)

**Purpose**: Technical debugging and comprehensive event tracking

**Prerequisites**: Developer Mode must be enabled

**Information Displayed**:
- Complete webhook payloads
- API request and response logs
- Timestamp for each event
- Log level (Info, Warning, Error)

**Use Case**: Essential for:
- Technical troubleshooting
- Verifying webhook delivery and processing
- Tracking transaction state changes
- Debugging integration issues
- Providing detailed information to support teams

For detailed information, see [Advanced Features Guide](docs/ADVANCED_FEATURES.md).


## Advanced Features

### Developer Mode Capabilities

Developer Mode provides access to advanced monitoring and debugging tools.

#### Enabling Developer Mode

1. Navigate to Settings
2. Scroll to Developer Tools section
3. Click "Activate the developer mode"

#### Available Features

##### Transaction Logs Tab

**Capabilities**:
- Complete webhook payload inspection
- API request and response tracking
- Event source identification
- Chronological event timeline with timestamps
- Log level filtering (Info, Warning, Error)

##### API Configuration Fields

**Capabilities**:
- Environment switching (Test/Production)
- Custom API URL configuration
- Custom webhook endpoint configuration

**WARNING**: API configuration should only be modified by technical personnel. Incorrect configuration will prevent payment processing.

### Automated Pending Transaction Handling

#### Overview

The module includes an automated process to maintain data integrity by handling transactions that remain in pending status.

#### Functionality

**Process**:
- Scheduled job runs every 15 minutes (default)
- Detects transactions in "Pending" status for more than 30 minutes
- Automatically updates status to "Error" if no webhook received
- Prevents incomplete transactions from remaining in the system indefinitely

**Configuration**:
- **Execution Frequency**: Every 15 minutes (configurable)
- **Timeout Threshold**: 30 minutes (hardcoded)
- **Activation Status**: 
  - Enabled by default (Odoo 18.0+)
  - Requires manual activation (Odoo 17.0)

#### Verification

To verify cron job status:

1. Navigate to: Settings → Technical → Automation → Scheduled Actions
2. Search for: "PaySolutions: Check Pending Transactions"
3. Verify "Active" checkbox is enabled


## Troubleshooting

### Common Issues and Solutions

#### Issue 1: Payment Not Updating After Completion

**Symptoms**:
- Customer completed payment but invoice remains in "Posted" status
- Transaction stuck in "Pending" status

**Resolution Steps**:

1. **Verify Webhook Configuration**:
   - Confirm webhook URL is correctly configured in PaySolutions merchant panel
   - Ensure webhook URL is publicly accessible via HTTPS
   - Test webhook endpoint accessibility

2. **Review Webhook Logs**:
   - Enable Developer Mode
   - Navigate to transaction → Logs tab
   - Search for "Webhook received" entries
   - If webhook not received: Issue with PaySolutions configuration
   - If webhook failed: Review error message in logs

3. **Manual Status Verification**:
   - Open transaction record
   - Click "Verify Payment Status (PaySolutions)" button
   - Review updated status

#### Issue 2: Invoice Not Marked as Paid

**Symptoms**:
- Transaction status shows "Confirmed"
- Invoice status remains "Posted" (not marked as paid)
- Payment received but not reconciled with invoice

**Resolution Steps**:

1. **Verify Journal Configuration**:
   - Navigate to: Accounting → Configuration → Journals → Bank
   - Select Incoming Payments tab
   - Locate PaySolutions payment method
   - Verify Outstanding Account is set to Bank Account (not Outstanding Receipts)
   - Refer to [Configuration Step 3](#step-3-configure-payment-journal-critical-for-auto-reconciliation)

2. **Confirm Webhook Receipt**:
   - Enable Developer Mode
   - Navigate to transaction → Logs tab
   - Verify "Payment COMPLETED" log entry exists

3. **Manual Reconciliation** (if needed):
   - Navigate to: Accounting → Customers → Invoices
   - Open the relevant invoice
   - Click "Register Payment"
   - Link to existing PaySolutions payment

#### Issue 3: Pending Transactions Not Automatically Updated

**Symptoms**:
- Transactions remain in "Pending" status beyond 30 minutes
- No automatic error status assignment

**Resolution Steps**:

1. **Verify Cron Job Status**:
   - Navigate to: Settings → Technical → Automation → Scheduled Actions
   - Search for: "PaySolutions: Check Pending Transactions"
   - Verify "Active" checkbox is enabled
   - Review "Last Run" field for recent execution
   - Click "Run Manually" to execute immediately

2. **Bulk Status Check**:
   - Navigate to: Payment Providers → PaySolutions
   - Click "Check Status Now" button
   - All pending transactions will be verified with gateway

3. **Individual Transaction Verification**:
   - Open specific transaction record
   - Click "Verify Payment Status (PaySolutions)" button

#### Issue 4: Webhook Authorization Verification Failed

**Symptoms**:
- Logs show "Authorization verification failed" error
- Webhooks received but not processed

**Resolution Steps**:

1. **Verify Secret Key**:
   - Ensure Secret Key in Odoo exactly matches PaySolutions merchant panel
   - Re-enter Secret Key carefully (no extra spaces)

2. **Verify Webhook Method**:
   - PaySolutions Merchant Panel → Return Parameter
   - Confirm PostBack Method is set to "POST" (not GET)

3. **Review Webhook Payload**:
   - Enable Developer Mode → Logs tab (Alternative: For Odoo.sh users, access the application logs directly via the Odoo.sh platform for more detailed information.)
   - Review webhook payload format
   - Contact PaySolutions support if payload format is unexpected

#### Issue 5: SSL/HTTPS Certificate Errors

**Symptoms**:
- Webhook delivery fails with SSL errors
- PaySolutions cannot connect to webhook URL

**Resolution Steps**:

1. **Verify SSL Certificate**:
   - Ensure valid SSL certificate installed on server
   - Certificate must not be self-signed for production
   - Verify certificate is not expired

2. **Test Webhook URL**:
   - Test webhook URL accessibility from external network
   - Ensure HTTPS (not HTTP) is configured

3. **Check Server Configuration**:
   - Verify firewall allows incoming HTTPS connections
   - Ensure web server properly configured for HTTPS

### Getting Additional Help

#### Self-Service Resources

1. Enable Developer Mode and review transaction Logs tab
2. Review module documentation and linked guides
3. Search Odoo Community Forum for similar issues

#### Contacting Support

When contacting support, provide the following information:

- Transaction reference number
- Complete error messages from Logs tab (screenshots or text)
- Odoo version (e.g., 18.0.1.0)
- Module version (e.g., 18.0.1.0.0)
- Detailed steps to reproduce the issue
- PaySolutions merchant ID (last 4 digits only)

---

## Changelog

### Version 19.0.1.0.0 (February 2, 2026)

**Initial Release for Odoo 19.0**

#### Features

**Payment Methods**:
- PromptPay QR Code payment support
- Credit/Debit Card processing (Visa, MasterCard, JCB, UnionPay, American Express)
- Internet Banking integration with major Thai banks
- E-Wallet support (TrueMoney Wallet, Alipay, WeChat Pay, PayPal)
- Installment payment plans

**Technical Capabilities**:
- Multi-currency support: THB, USD, JPY, SGD, HKD, EUR, GBP, AUD, CHF
- Multi-language interface: Thai, English, Japanese
- Webhook-based payment confirmation
- Configurable automatic invoice reconciliation
- Quick action buttons (PaySolutions Transactions, Check Status Now)
- Transaction monitoring tools (Verify Payment Status, Message Status, PaySolutions Details)
- Developer Mode debugging capabilities (Logs tab with webhook payloads)
- Automated pending transaction cleanup (15-minute intervals)
- PCI DSS v4.0.1 compliance
- Comprehensive logging and audit trail

**Technical Implementation**:
- Odoo 19.0 compatibility
- Webhook-first architecture
- Session-based transaction tracking
- 12-digit reference number generation
- Proper authentication headers (merchantID, merchantSecretKey, apikey)

---

## Contributing

Contributions to this module are welcome. Please refer to our [Contributing Guidelines](CONTRIBUTING.md) for detailed information.

### Ways to Contribute

- Report bugs via [GitHub Issues](https://github.com/KotchasaanTechnologyInvention/payment_paysolutions/issues)
- Submit feature requests
- Improve documentation
- Submit pull requests for bug fixes or enhancements
- Provide feedback and suggestions

### Code Contribution Process

1. Fork the repository
2. Create a feature branch
3. Implement changes with appropriate tests
4. Submit pull request with detailed description
5. Address review comments

---

## Author

**Kotchasaan Technology Invention Co., Ltd.**

- Website: [https://kotchasaan.com](https://kotchasaan.com)
- Email: info@kotchasaan.com
- Location: Bangkok, Thailand

---

## License

This module is licensed under the GNU Lesser General Public License v3.0 (LGPL-3).

See [LICENSE](LICENSE) file for complete license text.

### License Summary

- Free to use, modify, and distribute
- May be used in commercial projects
- Modified versions must disclose source code
- Derivative works must use the same license (LGPL-3)

---

## Acknowledgments

- **PaySolutions Team**: For API support and comprehensive documentation
- **Odoo Community**: For the robust ERP platform and ecosystem
- **Contributors**: For improvements and enhancements to this module

---

## Disclaimer

This module is provided "as is" without warranty of any kind, either expressed or implied. Users are advised to:

- Conduct thorough testing in a staging environment before production deployment
- Maintain regular database backups before installing or upgrading
- Review security considerations relevant to their specific use case
- Consult PaySolutions merchant agreement for terms and conditions

The authors and contributors assume no liability for any damages or losses arising from the use of this module.

---

## Support and Contact Information

### Module Support

**Technical Issues**:
- Email: support@kotchasaan.com
- Bug Reports: [GitHub Issues](https://github.com/KotchasaanTechnologyInvention/payment_paysolutions/issues)
- Website: [Kotchasaan](https://kotchasaan.com/)

### PaySolutions Account Support

**Merchant Account Issues**:
- Email: support@paysolutions.asia
- Website: [https://paysolutions.asia](https://paysolutions.asia)
- Merchant Control Panel: [https://controls.paysolutions.asia](https://controls.paysolutions.asia)
- API Documentation: [https://api-docs.paysolutions.asia](https://api-docs.paysolutions.asia)

---
