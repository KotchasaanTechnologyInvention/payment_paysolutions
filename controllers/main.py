import logging
import pprint
from datetime import timedelta
from werkzeug.exceptions import Forbidden

from odoo import http, fields, _
from odoo import http
from odoo.http import request
from odoo.exceptions import ValidationError
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing

_logger = logging.getLogger(__name__)


class PaySolutionsController(http.Controller):
    """
    Controller for handling PaySolutions payment flow
    Integrates with Payment Transaction State Management
    """

    # === WEBHOOK ENDPOINT (STEP 3: PAYMENT RESULT PROCESSING) ===

    @http.route('/payment/paysolutions/webhook', type='http', auth='public',
                methods=['GET', 'POST'], csrf=False)
    def paysolutions_webhook(self, **post):
        """
        Handle PaySolutions webhook notification
        State transitions: PENDING -> DONE/ERROR/CANCELLED
        """
        _logger.info("PaySolutions webhook received")
        _logger.debug("Webhook data: %s", pprint.pformat(post))
        _logger.info("Webhook data: %s", pprint.pformat(post))
        _logger.info("Method: %s", request.httprequest.method)

        try:
            # Handle both GET and POST
            if request.httprequest.method == 'GET':
                data = post
                _logger.info("GET request - using query string parameters")
            else:
                json_data = request.httprequest.get_json(force=True, silent=True)
                if json_data:
                    data = json_data
                    _logger.info("POST request - using JSON body")
                else:
                    data = post
                    _logger.info("POST request - using form data")

            _logger.info(f"Process Webhook data: {pprint.pformat(data)}")

            # Get transaction from webhook data
            tx_sudo = self._get_transaction_from_webhook(data)
            if not tx_sudo:
                _logger.error("PaySolutions webhook: Transaction not found")
                return request.make_json_response({
                    'error': 'Transaction not found'
                }, status=404)

            # Validate webhook security
            if not self._validate_webhook_security(tx_sudo, data):
                _logger.error("PaySolutions webhook: Security validation failed")

            # Process webhook data and update transaction state
            tx_sudo.handle_paysolutions_webhook(data)

            # Commit the transaction state change
            request.env.cr.commit()

            # Trigger post-processing for UI updates
            PaymentPostProcessing.monitor_transaction(tx_sudo)

            _logger.info("PaySolutions webhook processed successfully for transaction %s",
                         tx_sudo.reference)

            return request.make_json_response({'status': 'OK'})

        except ValidationError as e:
            _logger.error("PaySolutions webhook validation error: %s", e)
            request.env.cr.rollback()
            return f"Validation Error: {str(e)}", 400

        except Exception as e:
            _logger.exception("PaySolutions webhook processing error: %s", e)
            request.env.cr.rollback()
            return f"Processing Error: {str(e)}", 500

    # === RETURN URL ENDPOINT (STEP 3B: USER RETURN FALLBACK) ===

    @http.route('/payment/paysolutions/return', type='http', auth='public',
                methods=['GET', 'POST'], website=True)
    def paysolutions_return(self, **kwargs):
        """
        Handle user return from PaySolutions payment page
        IMPORTANT: This should NOT process payment data or parameters
        According to PaySolutions docs, Return URL is for user navigation only
        All payment processing must happen via webhook (Post Back URL)
        """
        _logger.info("PaySolutions return received")
        _logger.debug("Return data (for logging only): %s", pprint.pformat(kwargs))

        tx_sudo = None
        if hasattr(request, 'session') and request.session.get('payment_tx_id'):
            tx_sudo = request.env['payment.transaction'].sudo().browse(
                request.session.get('payment_tx_id')
            )

        if not tx_sudo:
            # Find most recent PaySolutions transaction (fallback)
            tx_sudo = request.env['payment.transaction'].sudo().search([
                ('provider_code', '=', 'paysolutions'),
                ('state', 'in', ['pending', 'draft'])
            ], order='create_date desc', limit=1)
        
        # Redirect to existing status checking system
        if tx_sudo:
            request.session['last_payment_tx_id'] = tx_sudo.id
            request.session['last_payment_reference'] = tx_sudo.reference
            return request.redirect('/payment/status')
        else:
            # If no transaction found, redirect to general payment status
            return request.redirect('/payment/status')

    # === UTILITY METHODS ===

    def _get_transaction_from_webhook(self, webhook_data):
        """Extract transaction from PaySolutions webhook data"""
        refno = webhook_data.get('refno')
        if not refno:
            _logger.error("PaySolutions webhook missing refno")
            return None

        # Find transaction by PaySolutions refno
        tx_sudo = request.env['payment.transaction'].sudo().search([
            ('paysolutions_refno', '=', refno),
            ('provider_code', '=', 'paysolutions')
        ], limit=1)

        if not tx_sudo:
            # Fallback: try to find by reference if refno doesn't match
            reference = webhook_data.get('reference')
            if reference:
                tx_sudo = request.env['payment.transaction'].sudo().search([
                    ('reference', '=', reference),
                    ('provider_code', '=', 'paysolutions')
                ], limit=1)

        return tx_sudo

    def _validate_webhook_security(self, transaction, webhook_data):
        """Validate PaySolutions webhook security"""
        try:
            # Basic validation: check required fields match
            if not webhook_data.get('refno'):
                _logger.error("PaySolutions webhook missing refno")
                return False
            
            if not webhook_data.get('merchantid'):
                _logger.error("PaySolutions webhook missing merchantid")
                return False
            
            # Validate merchantid matches configured value
            if webhook_data['merchantid'] != transaction.provider_id.paysolutions_merchant_id:
                _logger.error(
                    "PaySolutions merchantid mismatch: expected %s, got %s",
                    transaction.provider_id.paysolutions_merchant_id,
                    webhook_data['merchantid']
                )
                return False
            
            _logger.info("PaySolutions webhook security validation passed")
            return True

        except Exception as e:
            _logger.error("PaySolutions webhook security validation error: %s", e)
            return False
