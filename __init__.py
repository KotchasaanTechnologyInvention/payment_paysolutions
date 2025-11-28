from . import controllers
from . import models
from odoo.addons.payment import setup_provider, reset_payment_provider
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """
    Post-install hook for PaySolutions
    Uses Odoo's built-in setup_provider to safely configure provider
    """
    _logger.info("=== PaySolutions Post-Install Setup START ===")

    try:
        # Use built-in setup_provider function (like Stripe does)
        # This handles payment method linking safely
        setup_provider(env, 'paysolutions')
        _logger.info("Setup provider completed")

        # Get provider for additional setup
        provider = env['payment.provider'].search([('code', '=', 'paysolutions')], limit=1)

        if not provider:
            _logger.error("PaySolutions provider not found after setup!")
            return

        # Verify payment method is now active
        payment_method = env['payment.method'].search([('code', '=', 'paysolutions')], limit=1)
        if payment_method:
            _logger.info("Payment method active: %s", payment_method.active)
            _logger.info("Linked to %d provider(s)", len(payment_method.provider_ids))

        # Setup journal for payment reconciliation
        if not provider.journal_id:
            # Try to find existing bank journal
            journal = env['account.journal'].search([
                ('type', '=', 'bank'),
                ('company_id', '=', provider.company_id.id)
            ], limit=1)

            if not journal:
                # Create new bank journal for PaySolutions
                journal = env['account.journal'].create({
                    'name': 'PaySolutions Bank',
                    'code': 'PAYS',
                    'type': 'bank',
                    'company_id': provider.company_id.id,
                })
                _logger.info("Created new journal: %s", journal.name)

            # Link journal to provider
            provider.journal_id = journal.id
            _logger.info("Linked journal: %s to provider", journal.name)

        # Verify setup
        pm_count = len(provider.payment_method_ids)
        _logger.info("Provider has %d payment method(s): %s",
                    pm_count,
                    ', '.join(provider.payment_method_ids.mapped('code')))

        # Log journal info
        if provider.journal_id:
            _logger.info("Journal configured: %s (Code: %s)",
                        provider.journal_id.name,
                        provider.journal_id.code)

        _logger.info("=== PaySolutions Setup Complete ===")

    except Exception as e:
        _logger.error("PaySolutions setup failed: %s", e, exc_info=True)
        # Don't raise - allow module to install
        # User can fix configuration issues manually


def uninstall_hook(env):
    """Cleanup PaySolutions provider on module uninstall"""
    reset_payment_provider(env, 'paysolutions')