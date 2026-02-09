# Cloudflare Bot Protection Enablement Checklist

Short, safe rollout steps for Cloudflare Bot Fight Mode.

## Checklist

1. Inventory automated traffic (uptime monitors, webhooks, API clients, CI/CD hooks, partner crawlers).
2. Pick the right mode. Use Bot Fight Mode if no exceptions are needed. Use Super Bot Fight Mode with WAF Skip rules if exceptions are required.
3. Enable Bot Fight Mode in Cloudflare: Security -> Settings -> filter "Bot traffic" -> Bot Fight Mode -> On.
4. Monitor immediately after enabling in Security -> Events and confirm "Bot Fight Mode" actions.
5. Validate critical paths. Test human flows (home, auth, uploads, APIs). Confirm automated traffic still works; if not, switch to SBFM and add WAF Skip rules.
6. Rollback plan: toggle Bot Fight Mode Off if issues appear.
