import hashlib
import logging
import requests
from werkzeug import urls

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentProviderPaySolutions(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('paysolutions', 'PaySolutions')],
        ondelete={'paysolutions': 'set default'}
    )

    # === PAYSOLUTIONS CONFIGURATION FIELDS ===

    paysolutions_merchant_id = fields.Char(
        string="Merchant ID",
        help="The merchant ID provided by PaySolutions",
        required_if_provider='paysolutions'
    )

    paysolutions_secret_key = fields.Char(
        string="Secret Key",
        help="The secret key provided by PaySolutions for checksum generation",
        required_if_provider='paysolutions',
        groups='base.group_user'
    )

    paysolutions_api_key = fields.Char(
        string="API Key",
        help="The API key provided by PaySolutions for API calls",
        required_if_provider='paysolutions',
        groups='base.group_user'
    )

    paysolutions_payment_url = fields.Char(
        string="Payment URL",
        help="PaySolutions payment gateway URL",
        required_if_provider='paysolutions',
        default="https://payments.paysolutions.asia/payment"
    )

    paysolutions_api_url = fields.Char(
        string="API URL",
        help="PaySolutions API base URL for status queries and refunds",
        required_if_provider='paysolutions',
        default="https://apis.paysolutions.asia"
    )

    paysolutions_webhook_url = fields.Char(
        string="Webhook URL",
        help="PaySolutions webhook/callback URL for payment notifications",
        compute='_compute_paysolutions_webhook_url',
        readonly=True,
    )

    paysolutions_return_url = fields.Char(
        string="Return URL",
        help="This URL is for user navigation only and should NOT be used for payment verification.",
        compute='_compute_paysolutions_return_url',
        readonly=True,
    )

    # === COMPUTE METHODS ===

    @api.depends('code')
    def _compute_paysolutions_webhook_url(self):
        for provider in self:
            if provider.code == 'paysolutions':
                base_url = provider.get_base_url()
                provider.paysolutions_webhook_url = urls.url_join(
                    base_url, '/payment/paysolutions/webhook'
                )
            else:
                provider.paysolutions_webhook_url = False

    @api.depends('code')
    def _compute_paysolutions_return_url(self):
        for provider in self:
            if provider.code == 'paysolutions':
                base_url = provider.get_base_url()
                provider.paysolutions_return_url = urls.url_join(
                    base_url, '/payment/paysolutions/return'
                )
            else:
                provider.paysolutions_return_url = False

    # === CONSTRAINT METHODS ===

    @api.constrains('paysolutions_merchant_id')
    def _check_paysolutions_merchant_id(self):
        """Validate PaySolutions merchant ID format."""
        for provider in self:
            if provider.code == 'paysolutions' and provider.paysolutions_merchant_id:
                if not provider.paysolutions_merchant_id.isdigit():
                    raise ValidationError(_("PaySolutions Merchant ID must be numeric."))
                if len(provider.paysolutions_merchant_id) != 8:
                    raise ValidationError(_("PaySolutions Merchant ID must be 8 digits."))

    # === BUSINESS METHODS ===

    def _get_supported_currencies(self):
        """Return supported currencies for PaySolutions."""
        if self.code != 'paysolutions':
            return super()._get_supported_currencies()

        # PaySolutions supports multiple currencies
        supported_currencies = ['THB', 'USD', 'EUR', 'GBP', 'AUD', 'SGD', 'HKD', 'JPY', 'CHF']
        return self.env['res.currency'].search([('name', 'in', supported_currencies)])

    def _get_default_payment_method_codes(self):
        """Return default payment method codes for PaySolutions."""
        if self.code != 'paysolutions':
            return super()._get_default_payment_method_codes()

        # PaySolutions supports these payment methods mapped to channels
        return ['paysolutions']

    def _compute_feature_support_fields(self):
        """Override to enable PaySolutions features"""
        super()._compute_feature_support_fields()

        # Set PaySolutions feature support
        self.filtered(lambda p: p.code == 'paysolutions').update({
            'support_refund': 'partial',  # Support partial refunds
            'support_tokenization': False,  # No tokenization
            'support_express_checkout': False,  # No express checkout
            'support_manual_capture': False,  # Auto capture only
        })

    def _is_tokenization_required(self, **kwargs):
        """PaySolutions doesn't support tokenization."""
        if self.code != 'paysolutions':
            return super()._is_tokenization_required(**kwargs)
        return False

    def _should_build_inline_form(self, is_validation=False):
        """PaySolutions uses redirect flow only."""
        if self.code != 'paysolutions':
            return super()._should_build_inline_form(is_validation)
        return False

    def _get_redirect_form_view(self, is_validation=False):
        """Return the redirect form template for PaySolutions."""
        if self.code != 'paysolutions':
            return super()._get_redirect_form_view(is_validation)
        return self.env.ref('payment_paysolutions.paysolutions_redirect_form')

    # === PAYSOLUTIONS API METHODS ===

    def _make_paysolutions_request(self, endpoint, data, method='POST'):
        """Make API request to PaySolutions."""
        self.ensure_one()

        if not self.paysolutions_api_url:
            raise ValidationError(_("PaySolutions API URL not configured"))

        url = f"{self.paysolutions_api_url.rstrip('/')}/{endpoint.lstrip('/')}"

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'Odoo-PaySolutions/1.0'
        }

        # Add API key if available
        if self.paysolutions_api_key:
            headers['Authorization'] = f"Bearer {self.paysolutions_api_key}"

        try:
            _logger.info("Making PaySolutions API request to %s", url)
            _logger.debug("Request data: %s", data)

            if method == 'GET':
                response = requests.get(url, params=data, headers=headers, timeout=30)
            else:
                response = requests.post(url, json=data, headers=headers, timeout=30)

            response.raise_for_status()
            result = response.json()

            _logger.info("PaySolutions API response received")
            _logger.debug("Response data: %s", result)

            return result

        except requests.exceptions.ConnectionError as e:
            _logger.error("PaySolutions API connection error: %s", str(e))
            raise ValidationError(_("Failed to connect to PaySolutions API. Please check your network connection."))

        except requests.exceptions.Timeout:
            _logger.error("PaySolutions API request timeout")
            raise ValidationError(_("PaySolutions API request timed out. Please try again."))

        except requests.exceptions.HTTPError as e:
            _logger.error("PaySolutions API HTTP error: %s",
                          e.response.status_code if hasattr(e, 'response') else str(e))
            raise ValidationError(_("PaySolutions API error: %s") % str(e))

        except requests.exceptions.RequestException as e:
            _logger.error("PaySolutions API request error: %s", str(e))
            raise ValidationError(_("PaySolutions API request failed: %s") % str(e))

        except ValueError as e:
            _logger.error("PaySolutions API returned invalid JSON: %s", str(e))
            raise ValidationError(_("Invalid response from PaySolutions API"))

        except Exception as e:
            # Catch any other exceptions (like in tests with mocked errors)
            _logger.error("PaySolutions API unexpected error: %s", str(e))
            raise ValidationError(_("PaySolutions API request failed: %s") % str(e))

    def query_paysolutions_payment_status(self, transaction_reference):
        self.ensure_one()

        # Prepare API request
        url = f"{self.paysolutions_api_url.rstrip('/')}/order/orderdetailpost"

        merchant_id_short = self.paysolutions_merchant_id[-5:] if self.paysolutions_merchant_id else ''

        headers = {
            'Content-Type': 'application/json',
            'merchantID': merchant_id_short,
            'merchantSecretKey': self.paysolutions_secret_key,
            'apikey': self.paysolutions_api_key,
        }

        query_data = {
            'merchantid': merchant_id_short,
            'refno': transaction_reference,
        }

        _logger.info("Result Test Inquiry  %s  %s", headers, query_data)

        try:
            _logger.info("Querying PaySolutions status for refno: %s", transaction_reference)

            response = requests.post(url, json=query_data, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()
            _logger.info("Inquiry data: %s", result)

            if isinstance(result, list):
                if not result:
                    _logger.warning("PaySolutions API returned empty list for refno %s", transaction_reference)
                    return None
                result = result[0]
                _logger.info("Extracted data from list: %s", result)

            if not isinstance(result, dict):
                _logger.error("PaySolutions API returned unexpected format: %s (type: %s)", result, type(result))
                return None

            return {
                'status': result.get('Status', 'unknown'),  # Status code (CP, PE, FL, CN)
                'status_name': result.get('StatusName', ''),  # Full status name
                'refno': result.get('ReferenceNo', transaction_reference),
                'order_no': result.get('OrderNo', ''),
                'total': float(result.get('Total', 0.0)),
                'merchantid': str(result.get('MerchantID', '')),
            }

        except requests.exceptions.HTTPError as e:
            _logger.error("PaySolutions API HTTP error %s for refno %s",
                          e.response.status_code if hasattr(e, 'response') else 'unknown',
                          transaction_reference)
            if hasattr(e, 'response') and e.response is not None:
                _logger.error("Response body: %s", e.response.text)
            return None
        
        except (ValueError, TypeError, KeyError) as e:
            _logger.error(
                "PaySolutions API response parsing error for refno %s: %s",
                transaction_reference, str(e)
            )
            return None                 

        except Exception as e:
            _logger.error("Failed to query PaySolutions status for %s: %s",
                          transaction_reference, e)
            return None
        
    # === PAYSOLUTIONS STATISTICS & REPORTING ===

    def action_view_paysolutions_transactions(self):
        self.ensure_one()
        
        if self.code != 'paysolutions':
            return
        
        # Count transactions by state
        Transaction = self.env['payment.transaction']
        
        total_count = Transaction.search_count([
            ('provider_id', '=', self.id),
            ('provider_code', '=', 'paysolutions')
        ])
        
        pending_count = Transaction.search_count([
            ('provider_id', '=', self.id),
            ('provider_code', '=', 'paysolutions'),
            ('state', '=', 'pending')
        ])
        
        done_count = Transaction.search_count([
            ('provider_id', '=', self.id),
            ('provider_code', '=', 'paysolutions'),
            ('state', '=', 'done')
        ])
        
        error_count = Transaction.search_count([
            ('provider_id', '=', self.id),
            ('provider_code', '=', 'paysolutions'),
            ('state', '=', 'error')
        ])
        
        canceled_count = Transaction.search_count([
            ('provider_id', '=', self.id),
            ('provider_code', '=', 'paysolutions'),
            ('state', '=', 'cancel')
        ])
        
        _logger.info(
            "PaySolutions stats for provider %s: Total=%s, Pending=%s, Done=%s, Error=%s, Canceled=%s",
            self.name, total_count, pending_count, done_count, error_count, canceled_count
        )
        
        return {
            'name': _('PaySolutions Transactions'),
            'type': 'ir.actions.act_window',
            'res_model': 'payment.transaction',
            'view_mode': 'list,kanban,form',
            'domain': [
                ('provider_id', '=', self.id),
                ('provider_code', '=', 'paysolutions')
            ],
            'context': {
                'default_provider_id': self.id,
                'search_default_group_by_state': 1,
            }
        }

    def action_check_pending_paysolutions_now(self):
        self.ensure_one()
        
        if self.code != 'paysolutions':
            return
        
        # Find all pending transactions for this provider
        pending_txs = self.env['payment.transaction'].search([
            ('provider_id', '=', self.id),
            ('provider_code', '=', 'paysolutions'),
            ('state', '=', 'pending')
        ])
        
        if not pending_txs:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('No Pending Transactions'),
                    'message': _('There are no pending PaySolutions transactions to check.'),
                    'type': 'info',
                    'sticky': False,
                }
            }
        
        # Check status for each pending transaction
        checked_count = 0
        updated_count = 0
        
        for tx in pending_txs:
            try:
                result = self.query_paysolutions_payment_status(tx.paysolutions_refno)
                
                if result:
                    old_state = tx.state
                    tx._process_paysolutions_status_update(result, timeout_minutes=None, source='manual')
                    
                    if tx.state != old_state:
                        updated_count += 1
                    
                    checked_count += 1
                    
            except Exception as e:
                _logger.error("Error checking PaySolutions tx %s: %s", tx.reference, e)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Status Check Complete'),
                'message': _('Checked %s transactions, %s updated.') % (checked_count, updated_count),
                'type': 'success',
                'sticky': False,
            }
        }

