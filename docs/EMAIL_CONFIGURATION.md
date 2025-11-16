# Email Configuration Guide

Knowledge Navigator supports sending transactional emails (invitations, password resets, etc.) via SMTP.

## Overview

The email sending service is **disabled by default**. To enable it, you need to configure SMTP settings in your backend configuration.

## Configuration

### Environment Variables

Add these variables to your `.env` file in the `backend/` directory:

```bash
# Enable email sending
SMTP_ENABLED=true

# SMTP Server Configuration
SMTP_HOST=smtp.gmail.com          # Your SMTP server hostname
SMTP_PORT=587                     # Port (587 for TLS, 465 for SSL)
SMTP_USE_TLS=true                 # Use TLS (true) or SSL (false)

# SMTP Authentication
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Use app password for Gmail

# Email From Address
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=Knowledge Navigator

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:3003
```

### Common SMTP Providers

#### Gmail

```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password  # Generate from Google Account > Security > App passwords
SMTP_FROM_EMAIL=your-email@gmail.com
SMTP_FROM_NAME=Knowledge Navigator
```

**Note**: For Gmail, you need to:
1. Enable 2-factor authentication (2FA)
2. Generate an "App Password" from Google Account Settings
3. Use the app password (not your regular password) in `SMTP_PASSWORD`

### How to Get Gmail App Password (Step-by-Step)

1. **Enable 2-Factor Authentication** (if not already enabled):
   - Go to [Google Account Security](https://myaccount.google.com/security)
   - Under "Signing in to Google", click "2-Step Verification"
   - Follow the prompts to enable 2FA (you'll need your phone)

2. **Generate App Password**:
   - Go to [Google Account App Passwords](https://myaccount.google.com/apppasswords)
   - Or navigate: Google Account → Security → 2-Step Verification → App passwords
   - You may need to sign in again
   - Select "Mail" as the app
   - Select "Other (Custom name)" as the device
   - Enter a name (e.g., "Knowledge Navigator")
   - Click "Generate"
   - **Copy the 16-character password** (it will look like: `abcd efgh ijkl mnop` with spaces)
   - ⚠️ **Important**: You can only see this password once! Save it immediately.

3. **Use in Configuration**:
   - **Remove ALL spaces** from the password
   - Google shows it as: `abcd efgh ijkl mnop` (with spaces for readability)
   - You need: `abcdefghijklmnop` (no spaces)
   - Use it in `SMTP_PASSWORD` in your `.env` file
   - **Important**: Do NOT use quotes around the password in `.env` file
   - Example: `SMTP_PASSWORD=abcdefghijklmnop` (not `SMTP_PASSWORD="abcdefghijklmnop"`)
   
   **Quick tip**: Copy the password, paste it in a text editor, use Find & Replace to remove all spaces, then copy the result to your `.env` file.

**Alternative Method** (if App Passwords link doesn't appear):
- Make sure 2FA is enabled
- Try accessing directly: https://myaccount.google.com/apppasswords
- If still not visible, you may need to use "Less secure app access" (not recommended) or OAuth instead

#### Outlook/Office 365

```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-email@outlook.com
SMTP_PASSWORD=your-password
SMTP_FROM_EMAIL=your-email@outlook.com
SMTP_FROM_NAME=Knowledge Navigator
```

#### SendGrid

```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=apikey
SMTP_PASSWORD=your-sendgrid-api-key
SMTP_FROM_EMAIL=your-verified-sender@example.com
SMTP_FROM_NAME=Knowledge Navigator
```

#### Mailgun

```bash
SMTP_ENABLED=true
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=your-mailgun-smtp-username
SMTP_PASSWORD=your-mailgun-smtp-password
SMTP_FROM_EMAIL=your-verified-domain@mailgun.org
SMTP_FROM_NAME=Knowledge Navigator
```

## Testing Email Configuration

After configuring SMTP, you can test it by:

1. **Creating a new user with invitation email**:
   - Go to `/admin/users/new`
   - Fill in user details
   - Check "Send invitation email"
   - Create the user
   - Check backend logs for email sending status

2. **Check backend logs**:
   ```bash
   # Look for these log messages:
   # ✅ Success: "Email sent successfully to user@example.com"
   # ❌ Failure: "Failed to send email to user@example.com: [error details]"
   ```

## Email Types

The system currently supports:

1. **User Invitation Emails**: Sent when an admin creates a new user with "Send invitation email" checked
   - Contains verification link
   - Allows user to set their password
   - Link expires in 7 days

2. **Password Reset Emails**: (To be implemented)
   - Sent when user requests password reset
   - Contains reset token link

3. **Email Verification**: (To be implemented)
   - Sent during user registration
   - Contains verification link

## Troubleshooting

### Email not sending

1. **Check SMTP configuration**:
   - Verify all required variables are set
   - Ensure `SMTP_ENABLED=true`
   - Check credentials are correct

2. **Check backend logs**:
   ```bash
   # Look for error messages in backend logs
   tail -f backend/logs/app.log  # or wherever your logs are
   ```

3. **Common issues**:
   - **Gmail**: Make sure you're using an App Password, not your regular password
   - **Port blocked**: Some networks block port 587/465. Try different port or use VPN
   - **Firewall**: Ensure SMTP ports are not blocked
   - **Authentication failed**: Double-check username and password
   - **TLS/SSL**: Try switching `SMTP_USE_TLS` between `true` and `false`

### Email sent but not received

1. **Check spam folder**
2. **Verify sender email is correct** (`SMTP_FROM_EMAIL`)
3. **Check email provider's sending limits** (e.g., Gmail has daily sending limits)
4. **Verify recipient email is valid**

## Security Considerations

1. **Never commit `.env` file** to version control
2. **Use App Passwords** for Gmail (not your main password)
3. **Use environment-specific credentials** (dev, staging, production)
4. **Consider using a dedicated email service** (SendGrid, Mailgun) for production
5. **Enable SPF/DKIM** for your domain to improve deliverability

## Production Recommendations

For production environments, consider:

1. **Dedicated Email Service**: Use SendGrid, Mailgun, AWS SES, or similar
2. **Email Templates**: Customize email templates in `backend/app/services/email_sender.py`
3. **Rate Limiting**: Implement rate limiting for email sending
4. **Email Queue**: Use a background job queue (Celery, RQ) for async email sending
5. **Monitoring**: Set up alerts for email sending failures
6. **Bounce Handling**: Implement bounce and complaint handling

## Next Steps

- [ ] Configure SMTP settings in `.env`
- [ ] Test email sending with a test user
- [ ] Customize email templates if needed
- [ ] Set up monitoring for email delivery
- [ ] Configure SPF/DKIM for your domain (production)

