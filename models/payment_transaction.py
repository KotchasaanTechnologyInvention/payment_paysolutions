import logging
import pprint
import re
import time
import random
from datetime import datetime, timedelta
from werkzeug import urls
from odoo.http import request

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    # === PAYSOLUTIONS-SPECIFIC FIELDS ===

    paysolutions_payment_id = fields.Char(
        string="PaySolutions Payment ID",
        help="The payment ID assigned by PaySolutions",
        readonly=True
    )

    paysolutions_refno = fields.Char(
        string="PaySolutions Reference",
        help="The numeric reference number sent to PaySolutions",
        readonly=True
    )

    paysolutions_payment_status = fields.Char(
        string="PaySolutions Status",
        help="The payment status from PaySolutions",
        readonly=True
    )

    paysolutions_product_detail = fields.Char(
        string="PaySolutions Product Details",
        readonly=True
    )

    paysolutions_cardtype = fields.Char(
        string="PaySolutions Card Type",
        readonly=True
    )

    paysolutions_received_amount = fields.Monetary(
        string="Amount Received from PaySolutions",
        readonly=True,
        currency_field='currency_id',
        help="Actual amount received from PaySolutions (may include fees)"
    )

    log_ids = fields.One2many(
        'payment.transaction.log',
        'transaction_id',
        string='Logs'
    )

    def _add_log(self, message, level='info', source='api'):
        self.ensure_one()
        self.env['payment.transaction.log'].create({
            'transaction_id': self.id,
            'state_at_log': self.state,
            'level': level,
            'source': source,
            'message': message,
        })

    def action_set_to_canceled(self):
        for tx in self:
            tx._set_canceled()
        return True

    # === STATE MANAGEMENT FOR PAYSOLUTIONS REDIRECT FLOW ===

    def initiate_paysolutions_payment(self):
        """
        Step 2: DRAFT -> PENDING and generate redirect URL
        PaySolutions specific implementation
        """
        self.ensure_one()

        if self.provider_code != 'paysolutions':
            return super().initiate_paysolutions_payment()

        # Validate transaction state before initiating
        if self.state not in ('draft', 'pending'):
            raise ValidationError(_("Transaction must be in draft or pending state to initiate payment"))
        
        group_key = self._get_so_group_key()
        if group_key:
            old_txs = self.search([
                ('id', '!=', self.id),
                ('provider_code', '=', 'paysolutions'),
                ('state', '=', 'pending'),
                ('sale_order_ids.name', '=like', f'{group_key}%'),
            ])

            for tx in old_txs:
                _logger.warning(
                    "Invalidate old PaySolutions tx %s because new tx %s was created",
                    tx.reference, self.reference
                )
                tx._set_canceled(_(
                    "A new payment process has been initiated. "
                    "Please proceed with the latest transaction only."
                ))

        # Use existing reference as refno instead of generating new one
        if not self.paysolutions_refno:
            # For PaySolutions, reference should already be 12-digit numeric from _compute_reference()
            self.paysolutions_refno = self._generate_paysolutions_refno()
            _logger.info("Setting paysolutions_refno to existing reference: %s", self.paysolutions_refno)

        if self.state == 'draft':
            self._set_pending(_("PaySolutions payment initiated"))
            self.write({
                'provider_reference': self.paysolutions_refno,
            })

        # Generate PaySolutions redirect data
        redirect_data = self._get_paysolutions_payment_data()

        _logger.info("PaySolutions transaction %s set to PENDING, refno: %s",
                     self.reference, self.paysolutions_refno)

        return redirect_data

    # === PROCESSING METHODS ===

    def _get_specific_rendering_values(self, processing_values):
        """Override to return PaySolutions-specific rendering values for redirect payment"""
        res = super()._get_specific_rendering_values(processing_values)

        if self.provider_code != 'paysolutions':
            return res
        
        # For PaySolutions, we need to create transaction first, then get redirect data
        if self.state in ('draft', 'pending'):
            redirect_data = self.initiate_paysolutions_payment()

            return {
                'api_url': self.provider_id.paysolutions_payment_url,
                **redirect_data,
            }
        else:
            # Transaction already initiated
            redirect_data = self._get_paysolutions_payment_data()

            return {
                'api_url': self.provider_id.paysolutions_payment_url,
                **redirect_data,
            }

    def _get_paysolutions_payment_data(self):
        """Generate PaySolutions payment form data based on official API documentation"""
        self.ensure_one()

        if self.provider_code != 'paysolutions':
            return {}

        if not self.paysolutions_refno:
            self.paysolutions_refno = self._get_paysolutions_payment_data()

        amount = "{:.2f}".format(float(self.amount))
        product_detail = self.detail_format()
        paysolutions_lang = self._get_paysolutions_language()

        # PaySolutions API standard fields
        payment_data = {
            # Required main parameters
            'merchantid': self.provider_id.paysolutions_merchant_id,
            'refno': self.paysolutions_refno,
            'customeremail': self.partner_id.email or 'customer@example.com',
            'productdetail': product_detail,
            'total': amount,
            'paysolutions_lang': paysolutions_lang,
            'cc': self._get_paysolutions_currency_code(),
        }

        _logger.info("Generated PaySolutions payment data for transaction %s", self.reference)
        _logger.debug("PaySolutions payment_data: %s", pprint.pformat(payment_data))

        return payment_data
    
    def _get_paysolutions_language(self):
        if hasattr(request, 'httprequest'):
            frontend_lang = request.httprequest.cookies.get('frontend_lang')
            if frontend_lang:
                odoo_lang = frontend_lang 
                _logger.info("Language from website selector cookie: %s", frontend_lang)
            else:
                odoo_lang = request.env.context.get('lang', 'en_US')
                _logger.info("Language from context (fallback): %s", odoo_lang)
        else:
            odoo_lang = request.env.user.lang or 'en_US'
            _logger.info("Language from user (fallback): %s", odoo_lang)
        
        lang_map = {
            'en_US': 'EN',
            'en_GB': 'EN',
            'th_TH': 'TH',
            'ja_JP': 'JP',
        }
        
        paysolutions_lang = lang_map.get(odoo_lang, 'EN')
        
        _logger.info("Detected website language: %s → PaySolutions lang: %s", 
                    odoo_lang, paysolutions_lang)
        
        return paysolutions_lang

    def _get_paysolutions_currency_code(self):
        """Convert Odoo currency to PaySolutions currency code"""
        currency_mapping = {
            'THB': '00', 'USD': '01', 'JPY': '02', 'SGD': '03',
            'HKD': '04', 'EUR': '05', 'GBP': '06', 'AUD': '07', 'CHF': '08',
        }
        currency_code = self.currency_id.name if self.currency_id else 'THB'
        return currency_mapping.get(currency_code, '00')

    # === WEBHOOK PROCESSING (INTEGRATION WITH STATE MANAGEMENT) ===

    def handle_paysolutions_webhook(self, webhook_data):
        """
        Step 3: Handle PaySolutions webhook and update transaction state
        Integrates with our state management system
        """
        self.ensure_one()

        _logger.info("Processing PaySolutions webhook for transaction %s", self.reference)
        _logger.debug("PaySolutions webhook data: %s", pprint.pformat(webhook_data))
        self._add_log(
            f"Webhook received:\n{pprint.pformat(webhook_data)}",
            source='webhook'
        )

        try:
            # Validate webhook data
            self._validate_paysolutions_webhook(webhook_data)

            paysolutions_refno = webhook_data.get('refno') or webhook_data.get('paysolutions_refno')
            if paysolutions_refno:
                self.provider_reference = paysolutions_refno
                _logger.info("Updated provider_reference with PaySolutions refno: %s", paysolutions_refno)

            # Update PaySolutions-specific fields
            if 'orderno' in webhook_data:
                self.paysolutions_payment_id = webhook_data['orderno']
            if 'status' in webhook_data:
                self.paysolutions_payment_status = webhook_data['statusname']
            if 'productdetail' in webhook_data:
                self.paysolutions_product_detail = webhook_data['productdetail']
            if 'cardtype' in webhook_data:
                self.paysolutions_cardtype = webhook_data['cardtype']
            if 'total' in webhook_data:
                received_amount = float(webhook_data['total'])
                self.write({
                    'paysolutions_received_amount': received_amount
                })
                _logger.info(
                    "PaySolutions received amount: %.2f (Invoice: %.2f, Difference: %.2f)",
                    received_amount, self.amount, received_amount - self.amount
                )


            self._add_log("Webhook received", source='webhook')
        
            self._process_paysolutions_status_update(
                webhook_data, 
                timeout_minutes=None,
                source='webhook'
            )
            
            _logger.info(
                "PaySolutions webhook processed successfully for %s (Final state: %s)",
                self.reference, self.state
            )

        except Exception as e:
            _logger.error("Error processing PaySolutions webhook for %s: %s",
                        self.reference, e, exc_info=True)
            self._set_error(f"PaySolutions webhook processing error: {str(e)}")
            self._add_log(
                f"Webhook processing FAILED: {str(e)}", 
                level='error', 
                source='webhook'
            )
            raise

    def handle_paysolutions_return(self, return_data):
        """
        Step 3b: Handle user return from PaySolutions (fallback)
        Used when webhook is delayed or fails
        """
        self.ensure_one()

        _logger.info("Processing PaySolutions return for transaction %s", self.reference)
        self._add_log(
            f"User returned from PaySolutions:\n{return_data}",
            source='return'
        )

        # Only process return if transaction is still pending
        if self.state == 'pending':
            
            # Convert return data to webhook format and process
            webhook_format = {
                'result': return_data.get('status', 'unknown'),
                'refno': return_data.get('refno', self.paysolutions_refno),
                'message': return_data.get('message', ''),
            }

            self.handle_paysolutions_webhook(webhook_format)
        else:
            _logger.info("PaySolutions return ignored - transaction %s already in state %s",
                         self.reference, self.state)

    def _validate_paysolutions_webhook(self, webhook_data):
        """Validate PaySolutions webhook data"""
        # Check required fields
        if not webhook_data.get('refno'):
            raise ValidationError(_("PaySolutions webhook missing refno"))

        # Validate refno matches
        if webhook_data['refno'] != self.paysolutions_refno:
            raise ValidationError(_(
                "PaySolutions refno mismatch: expected %s, got %s",
                self.paysolutions_refno, webhook_data['refno']
            ))

        # Validate merchant ID if present
        if 'merchantid' in webhook_data:
            if webhook_data['merchantid'] != self.provider_id.paysolutions_merchant_id:
                raise ValidationError(_(
                    "PaySolutions merchant ID mismatch: expected %s, got %s",
                    self.provider_id.paysolutions_merchant_id, webhook_data['merchantid']
                ))

        # Validate amount if present
        # if 'total' in webhook_data:
        #     received_amount = float(webhook_data['total'])
        #     if abs(received_amount - self.amount) > 0.01:  # Allow small floating point differences
        #         raise ValidationError(_(
        #             "PaySolutions amount mismatch: expected %s, got %s",
        #             self.amount, received_amount
        #         ))

    # === PAYMENT STATE HANDLERS (INHERITED FROM MAIN STATE MANAGEMENT) ===

    def _handle_successful_payment(self):
        # PaySolutions-specific success actions
        if self.provider_code == 'paysolutions':
            # Log PaySolutions payment completion
            self.message_post(
                body=_(
                    "PaySolutions payment completed successfully.<br/>"
                    "Reference: %s<br/>"
                    "Status: %s"
                ) % (
                         self.paysolutions_refno or 'N/A',
                         self.paysolutions_payment_status or 'N/A'
                     )
            )
            _logger.info("PaySolutions payment success: %s", self.reference)

    def _handle_pending_payment(self):
        if self.provider_code == 'paysolutions':
            self.message_post(
                body=_(
                    "PaySolutions payment is pending confirmation.<br/>"
                    "Reference: %s"
                ) % (self.paysolutions_refno or 'N/A')
            )
            _logger.info("PaySolutions payment pending: %s", self.reference)

    def _handle_failed_payment(self):
        if self.provider_code == 'paysolutions':
            # Log detailed PaySolutions failure info
            self.message_post(
                body=_(
                    "PaySolutions payment failed.<br/>"
                    "Status: %s<br/>"
                    "Reference: %s<br/>"
                    "Error: %s"
                ) % (
                         self.paysolutions_payment_status or 'Unknown',
                         self.paysolutions_refno or 'N/A',
                         self.state_message or 'No error message'
                     )
            )
            _logger.info("PaySolutions payment failed: %s", self.reference)

    def _handle_cancelled_payment(self):
        """PaySolutions-specific cancellation handling (no super call)"""
        if self.provider_code == 'paysolutions':
            self.message_post(
                body=_(
                    "PaySolutions payment was cancelled.<br/>"
                    "Reference: %s"
                ) % (self.paysolutions_refno or 'N/A')
            )
            _logger.info("PaySolutions payment cancelled: %s", self.reference)

    # === UTILITY METHODS ===

    @api.model
    def _validate_paysolutions_data(self, payment_data):
        """Validate PaySolutions payment data before creating transaction"""
        required_fields = ['provider_id', 'amount', 'currency_id', 'partner_id']
        for field in required_fields:
            if not payment_data.get(field):
                raise ValidationError(_("Missing required field: %s") % field)

        # Validate amount range (PaySolutions limit: max 9,999,999)
        if payment_data['amount'] > 9999999:
            raise ValidationError(_("Amount exceeds PaySolutions limit of 9,999,999"))

        if payment_data['amount'] <= 0:
            raise ValidationError(_("Amount must be positive"))

    # === REFUND METHODS (IMPROVED) ===

    def _send_refund_request(self, amount_to_refund=None, create_refund_transaction=True):
        """Override to handle PaySolutions refunds with proper state management"""
        if self.provider_code != 'paysolutions':
            return super()._send_refund_request(amount_to_refund, create_refund_transaction)

        if self.state != 'done':
            raise UserError(_("Can only refund completed payments"))

        refund_amount = amount_to_refund or self.amount

        try:
            # Create refund transaction first
            if create_refund_transaction:
                refund_tx = self._create_child_transaction(refund_amount, is_refund=True)
                refund_tx._set_pending(_("PaySolutions refund initiated"))

            # For now, PaySolutions requires manual refund
            # In production, implement actual API call here
            message = _(
                "PaySolutions refund of %s %s has been requested for transaction %s. "
                "Please process manually through PaySolutions dashboard."
            ) % (refund_amount, self.currency_id.name, self.reference)

            _logger.info(message)

            if create_refund_transaction:
                # Set refund transaction to manual review state
                refund_tx._set_error(_(
                    "Manual refund required - please process through PaySolutions dashboard"
                ))
                return refund_tx
            else:
                raise UserError(message)

        except Exception as e:
            _logger.error("PaySolutions refund failed for %s: %s", self.reference, e)
            if create_refund_transaction:
                refund_tx._set_error(f"PaySolutions refund error: {str(e)}")
                return refund_tx
            else:
                raise UserError(_("PaySolutions refund failed: %s") % str(e))

    @api.model
    def _generate_paysolutions_refno(self):
        """ Custom refno generation for Pay Solutions with format {12-digit-random}. """

        max_attempts = 100

        for attempt in range(max_attempts):
            random_number = random.randint(100000000000, 999999999999)
            refno = str(random_number)

            existing_tx = self.sudo().search([('paysolutions_refno', '=', refno)], limit=1)
            if not existing_tx:
                _logger.info(f"Generated Pay Solutions reference: {refno}")
                return refno

        timestamp_str = str(int(time.time() * 1000))[-12:]
        _logger.warning(
            f"Could not generate unique reference after {max_attempts} attempts, using fallback: {timestamp_str}")
        return timestamp_str

    def detail_format(self):

        if self.invoice_ids:
            desc = f'Payment for invoice {self.invoice_ids[0].name}'[:255]
        elif self.sale_order_ids:
            desc = f'Payment for Order {self.sale_order_ids[0].name}'[:255]
        else:
            desc = f'Payment {self.reference}'[:255]

        return desc

    # === For SO payment process ===

    def _reconcile_after_done(self):
        """Override to handle SO payment"""

        res = super()._reconcile_after_done()

        if self.provider_code != 'paysolutions':
            return res

        if self.invoice_ids:
            _logger.info("Processing direct invoice payment for tx %s", self.reference)
            for invoice in self.invoice_ids.filtered(lambda inv: inv.state == 'posted'):
                if invoice.payment_state != 'paid':
                    self._create_payment_for_invoice(invoice)
        elif self.sale_order_ids:
            _logger.info("Processing SO payment for tx %s", self.reference)
            for order in self.sale_order_ids:
                # Create invoice if not exists
                if not order.invoice_ids and order.state in ['sale', 'done']:
                    order._create_invoices()

                if order.invoice_ids:
                    for invoice in order.invoice_ids.filtered(lambda inv: inv.state == 'posted'):
                        self._create_payment_for_invoice(invoice)

        self._add_transaction_summary_log()

        return res

    def _create_payment_for_invoice(self, invoice):
        """Create account.payment and reconcile with invoice"""
        if invoice.payment_state in ['paid','in_payment'] :
            return
        
        payment_amount = self.paysolutions_received_amount or self.amount
        _logger.info(
            "Creating payment for invoice %s: Amount=%.2f (Invoice: %.2f, Received: %.2f)",
            invoice.name, payment_amount, invoice.amount_total, 
            self.paysolutions_received_amount or 0
        )

        self._add_log(
            f"Creating payment for Invoice {invoice.name}\n"
            f"Invoice Amount: {invoice.amount_total:.2f} {self.currency_id.name}\n"
            f"Payment Amount: {payment_amount:.2f} {self.currency_id.name}\n"
            f"Transaction Amount: {self.amount:.2f} {self.currency_id.name}",
            source='reconcile'
        )

        try:
            # Create payment
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice.partner_id.id,
                'amount': payment_amount,
                'currency_id': self.currency_id.id,
                'date': fields.Date.context_today(self),
                'journal_id': self.provider_id.journal_id.id,
                'payment_method_line_id': self._get_payment_method_line().id,
                'payment_reference': f'Payment for {invoice.name} via PaySolutions (Ref: {self.reference})',
            }

            payment = self.env['account.payment'].sudo().create(payment_vals)
            payment.action_post()

            payment_receivable_lines = payment.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
            )
            invoice_receivable_lines = invoice.line_ids.filtered(
                lambda line: line.account_id.account_type == 'asset_receivable'
            )
            lines_to_reconcile = payment_receivable_lines + invoice_receivable_lines

            if lines_to_reconcile:
                difference = payment_amount - invoice.amount_total

                log_message = (
                    f"✅ Invoice {invoice.name} reconciled successfully\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Invoice Amount:  {invoice.amount_total:>10.2f} {self.currency_id.name}\n"
                    f"Payment Amount:  {payment_amount:>10.2f} {self.currency_id.name}\n"
                    f"Difference:      {difference:>10.2f} {self.currency_id.name}\n"
                    f"Payment Record:  {payment.name}\n"
                    f"Journal:         {payment.journal_id.name}"
                )

                if abs(difference) > 0.01:
                    writeoff_acc = self.provider_id.paysolutions_writeoff_account_id

                    lines_to_reconcile.reconcile(
                        writeoff_acc_id=writeoff_acc.id,
                        writeoff_journal_id=payment.journal_id.id,
                        writeoff_label=f"PaySolutions Fee (Ref: {self.reference})"
                    )
                    log_message += (
                        f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"✅ Automated Adjustment Successful\n"
                        f"The difference of {difference:.2f} has been posted to account {writeoff_acc.code}."
                    )
                    _logger.info("PaySolutions: Auto write-off to %s", writeoff_acc.code)

                    self._add_log(log_message, level='info', source='reconcile')
                else:
                    lines_to_reconcile.reconcile()
                    if abs(difference) > 0.01:
                        log_message += (
                            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚠️ Amount difference detected!\n"
                            f"This may include payment gateway fees.\n"
                            f"Please adjust manually in Odoo accounting."
                        )
                        self._add_log(log_message, level='info', source='reconcile')
                        _logger.info("PaySolutions: Difference left for manual reconciliation")
                    else:
                        self._add_log(log_message, source='reconcile')
                        _logger.info("PaySolutions: Reconciled successfully (No difference)")

        except Exception as e:
            error_log = (
                f"❌ Failed to create payment for invoice {invoice.name}\n"
                f"Error: {str(e)}\n"
                f"Invoice Amount: {invoice.amount_total:.2f} {self.currency_id.name}\n"
                f"Payment Amount: {payment_amount:.2f} {self.currency_id.name}"
            )
            self._add_log(error_log, level='error', source='reconcile')
            _logger.error("Failed to create payment for invoice %s: %s", invoice.name, e)
            raise

    def _get_payment_method_line(self):
        """Get payment method line for journal"""
        method_line = self.env['account.payment.method.line'].search([
            ('journal_id', '=', self.provider_id.journal_id.id),
            ('name', '=', 'PaySolutions'),
            ('payment_type', '=', 'inbound')
        ], limit=1)

        if not method_line:
            # Fallback to any electronic method
            method_line = self.env['account.payment.method.line'].search([
                ('journal_id', '=', self.provider_id.journal_id.id),
                ('payment_type', '=', 'inbound')
            ], limit=1)

        return method_line
    
    def _get_pending_paysolutions_transactions(self, timeout_minutes=30):
        cutoff_time = fields.Datetime.now() - timedelta(minutes=timeout_minutes)
        return self.search([
            ('provider_code', '=', 'paysolutions'),
            ('state', '=', 'pending'),
            ('create_date', '<', cutoff_time)
        ])

    def _process_paysolutions_status_update(self, result, timeout_minutes=None, source='cron'):
        self.ensure_one()
        if not result:
            error_msg = "Payment verification failed - API/webhook returned None"
            if timeout_minutes:
                error_msg = f"Payment verification failed after {timeout_minutes} minutes"
            
            self._set_error(_(error_msg))
            self._add_log(error_msg, level='error', source='cron')
            _logger.error("PaySolutions tx %s verification failed - result is None", self.reference)
            return

        if 'total' in result:
            received_amount = float(result['total'])
            self.write({
                'paysolutions_received_amount': received_amount,
                'amount': received_amount,
            })
            self.env.cr.commit()

        status = result.get('status', '').upper()
        status_name = result.get('status_name', '')

        _logger.info("PaySolutions tx %s current status: %s (%s)", self.reference, status_name, status)

        source = 'webhook' if timeout_minutes is None else 'cron'

        # SUCCESS STATUSES
        if status in ['CP', 'Y', 'TC']:
            # CP = Completed
            # Y = Completed (alternative)
            # TC = Test Complete
            if source == 'webhook':
                self._set_done(_("PaySolutions: Payment completed successfully"))
                _logger.info(
                    "PaySolutions payment completed: %s (Status: %s, Payment ID: %s)",
                    self.reference, status_name, self.paysolutions_payment_id or 'N/A'
                )
                self._add_log(
                    f"Payment COMPLETED (status={status}, name={status_name})",
                    source='webhook'
                )
            else:
                self._set_done(_("Payment verified via status check"))
                _logger.info("PaySolutions tx %s completed (verified by cron)", self.reference)
                self._add_log(
                    f"Confirmed payment COMPLETED ({status} - {status_name})", 
                    source=source
                )

        # FAILED/REJECTED STATUSES
        elif status in ['RE', 'VR', 'PF']:
            # RE = Rejected
            # VR = VBV Rejected
            # PF = Payment Failed
            if source == 'webhook':
                error_msg = result.get('message') or status_name or 'Payment rejected'
                self._set_canceled(_("PaySolutions: %s") % error_msg)
                _logger.warning(
                    "PaySolutions payment rejected: %s (Status: %s - %s)",
                    self.reference, status, error_msg
                )
                self._add_log(
                    f"Payment CANCELLED (status={status}, reason={error_msg})",
                    level='warning',
                    source='webhook'
                )
            else:
                self._set_canceled(_("Payment rejected: %s") % (status_name or status))
                _logger.warning("PaySolutions tx %s timed out with status %s", self.reference, status)
                self._add_log(
                    f"Marked CANCELLED ({status} - {status_name})", 
                    level='warning', 
                    source=source
                )

        # CANCELLED STATUS
        elif status == 'C':
            # C = Cancel
            if source == 'webhook':
                self._set_canceled(_("PaySolutions: Payment cancelled by user"))
                _logger.info(
                    "PaySolutions payment cancelled: %s (Status: %s)",
                    self.reference, status_name
                )
            else:
                self._set_canceled(_("Payment cancelled by user"))
                _logger.warning("PaySolutions tx %s cancelled by user", self.reference)

        # REFUND STATUSES
        elif status in ['RF', 'VO']:
            # RF = Refund
            # VO = Voided
            # Note: Original payment was successful, now refunded
            if source == 'webhook':
                self._set_done(_("PaySolutions: Payment completed (later refunded)"))
                _logger.info(
                    "PaySolutions payment refunded: %s (Status: %s, Payment ID: %s)",
                    self.reference, status_name, self.paysolutions_payment_id or 'N/A'
                )
            else:
                self._set_done(_("Payment completed (later refunded): %s") % status_name)

        # IN-PROGRESS / PENDING STATUSES
        elif status in ['NS', 'N', 'VC', 'RR', 'HO']:
            # NS = Not Submit (customer at payment page)
            # N = Not Submit / UnPaid
            # VC = VBV Checking
            # RR = Request Refund (in progress)
            # HO = Hold (under review)
            if source == 'webhook':
                self._set_pending(_("PaySolutions: Payment in progress"))
                _logger.info(
                    "PaySolutions payment in progress: %s (Status: %s)",
                    self.reference, status_name
                )
            else:
                if timeout_minutes:
                    _logger.info(
                        "PaySolutions tx %s still in progress after %s minutes: %s, will check again",
                        self.reference, timeout_minutes, status_name
                    )
                    self._add_log(
                        f"Still PENDING after {timeout_minutes}min (status={status}, name={status_name})", 
                        level='warning', 
                        source=source
                    )

        # UNKNOWN STATUS
        else:
            if source == 'webhook':
                _logger.warning(
                    "Unknown PaySolutions status: %s (%s) for transaction %s",
                    status, status_name, self.reference
                )
                self._set_error(_("PaySolutions: Unknown payment status: %s") % (status_name or status))
                self._add_log(
                    f"UNKNOWN STATUS received: {status} / {status_name}",
                    level='error',
                    source='webhook'
                )
            else:
                error_msg = f"Payment not completed within {timeout_minutes} minutes. Status: {status_name or status}"
                self._set_error(_(error_msg))
                self._add_log(
                    f"UNKNOWN/ERROR STATUS: {status} / {status_name}", 
                    level='error', 
                    source=source
                )

    def _get_so_group_key(self):
        self.ensure_one()
        if not self.sale_order_ids:
            return False
        return self.sale_order_ids[0].name

    @api.model
    def _cron_check_pending_paysolutions(self):
        timeout_minutes = 30
        pending_txs = self._get_pending_paysolutions_transactions(timeout_minutes)

        _logger.info("Checking %s pending PaySolutions transactions", len(pending_txs))

        for tx in pending_txs:
            try:
                tx._add_log("Cron: start checking PaySolutions status", source='cron')
                result = tx.provider_id.query_paysolutions_payment_status(tx.paysolutions_refno)

                tx._process_paysolutions_status_update(result, timeout_minutes)

            except Exception as e:
                _logger.error("Error checking PaySolutions tx %s: %s", tx.reference, e)
                tx._add_log(f"Cron exception: {str(e)}", level='error', source='cron')

        _logger.info("Finished checking pending PaySolutions transactions")

    def action_paysolutions_manual_check(self):
        self.ensure_one()
        if self.provider_code != 'paysolutions':
            raise UserError("This action is only for PaySolutions.")

        result = self.provider_id.query_paysolutions_payment_status(self.paysolutions_refno)

        self._process_paysolutions_status_update(
            result,
            timeout_minutes=None,
            source='manual'
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Status Checked'),
                'message': _('Transaction status has been updated.'),
                'sticky': False,
            }
        }
    
    def _add_transaction_summary_log(self):
        """Add comprehensive transaction summary to log"""
        self.ensure_one()
        
        # Gather all transaction data
        invoice_info = "None"
        if self.invoice_ids:
            invoices = self.invoice_ids.mapped('name')
            invoice_info = ', '.join(invoices)
            total_invoice_amount = sum(self.invoice_ids.mapped('amount_total'))
        else:
            total_invoice_amount = 0
        
        so_info = "None"
        if self.sale_order_ids:
            orders = self.sale_order_ids.mapped('name')
            so_info = ', '.join(orders)
        
        # Calculate amounts
        tx_amount = self.amount
        received_amount = self.paysolutions_received_amount or 0
        difference = received_amount - tx_amount if received_amount else 0
        
        # Build comprehensive log
        log_message = f"""
    ═══════════════════════════════════════════════════════════
    TRANSACTION SUMMARY: {self.reference}
    ═══════════════════════════════════════════════════════════

    BASIC INFO:
    State:              {self.state}
    Provider:           {self.provider_id.name}
    Payment Method:     {self.payment_method_id.name if self.payment_method_id else 'N/A'}
    Customer:           {self.partner_id.name}
    Create Date:        {self.create_date}

    AMOUNTS:
    Transaction Amount: {tx_amount:>10.2f} {self.currency_id.name}
    Received Amount:    {received_amount:>10.2f} {self.currency_id.name}
    Difference:         {difference:>10.2f} {self.currency_id.name}
    
    RELATED DOCUMENTS:
    Invoices:           {invoice_info}
    Sale Orders:        {so_info}
    Total Invoice Amt:  {total_invoice_amount:>10.2f} {self.currency_id.name}

    PAYSOLUTIONS DATA:
    RefNo:              {self.paysolutions_refno or 'N/A'}
    Payment ID:         {self.paysolutions_payment_id or 'N/A'}
    Status:             {self.paysolutions_payment_status or 'N/A'}
    Card Type:          {self.paysolutions_cardtype or 'N/A'}
    Product Detail:     {self.paysolutions_product_detail or 'N/A'}

    STATUS:
    State Message:      {self.state_message or 'N/A'}
    Landing Route:      {self.landing_route or 'N/A'}

    ═══════════════════════════════════════════════════════════
    """
        
        # Add warning if there's amount difference
        if abs(difference) > 0.01:
            log_message += f"""
    ⚠️ WARNING: Amount Mismatch Detected
    Expected:  {tx_amount:.2f} {self.currency_id.name}
    Received:  {received_amount:.2f} {self.currency_id.name}
    Diff:      {difference:.2f} {self.currency_id.name}
    
    This may include payment gateway fees.
    Manual adjustment required in Odoo accounting.
    ═══════════════════════════════════════════════════════════
    """
        
        self._add_log(log_message.strip(), source='summary')


class PaymentTransactionLog(models.Model):
    _name = 'payment.transaction.log'
    _description = 'Payment Transaction Log'
    _order = 'create_date desc'

    transaction_id = fields.Many2one(
        'payment.transaction',
        required=True,
        ondelete='cascade',
        index=True
    )

    state_at_log = fields.Selection(
        selection=lambda self: self.env['payment.transaction']._fields['state'].selection,
    )

    source = fields.Selection(
        [
            ('cron', 'Cron'),
            ('webhook', 'Webhook'),
            ('return', 'Return'),
            ('redirect', 'Redirect'),
            ('api', 'API'),
            ('reconcile', 'Reconcile'),
            ('summary', 'Summary'),  
        ],
        default='api'
    )

    level = fields.Selection(
        [
            ('info', 'Info'),
            ('warning', 'Warning'),
            ('error', 'Error'),
        ],
        default='info'
    )

    message = fields.Text()
    create_date = fields.Datetime(readonly=True)