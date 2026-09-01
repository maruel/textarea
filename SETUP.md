# Deployment setup

Textarea is a static site. It does not need a build command, server, environment
variables, or API credentials.

## Cloudflare Pages

### Recommended: connect the Git repository

1. Push this repository to GitHub or GitLab.
2. In the [Cloudflare dashboard](https://dash.cloudflare.com/), open
   **Workers & Pages**.
3. Select **Create application** > **Pages** > **Connect to Git**.
4. Authorize the Git provider and select this repository.
5. Configure the deployment:

   | Setting | Value |
   | --- | --- |
   | Production branch | `main`, or the repository's default branch |
   | Framework preset | None |
   | Build command | Leave blank |
   | Build output directory | `public` |
   | Root directory | Leave blank |

6. Select **Save and Deploy**.

Cloudflare will publish the site at a URL such as
`https://<project>.pages.dev`. Future pushes to the production branch deploy
automatically; other branches receive preview deployments.

### Add a custom domain

After the first deployment:

1. Open the Pages project in **Workers & Pages**.
2. Select **Custom domains** > **Set up a domain**.
3. Enter the apex domain or subdomain and follow the DNS prompts.

For an apex domain such as `example.com`, the domain must use Cloudflare's
nameservers. For a subdomain managed by another DNS provider, create the CNAME
record Cloudflare requests. Add the domain through the Pages project before
creating a CNAME manually, or Cloudflare may not associate the hostname with
the deployment.

### Optional: deploy directly from a computer

Use a separate Direct Upload Pages project when Git-based deployments are not
wanted. With Node.js and npm installed, run from the repository root:

```sh
npx wrangler login
npx wrangler pages project create
npx wrangler pages deploy public
```

Wrangler prompts for the project name and production branch. Direct Upload
projects cannot later be converted to Git-integrated projects; create a new
Pages project if that deployment model changes.

### Verify the deployment

1. Open the generated `pages.dev` URL and enter text.
2. Reload the page and confirm the text remains in the URL hash.
3. Open the menu and select **Dictate** in a browser that supports the Web
   Speech API.
4. Allow microphone access and confirm recognized text appears at the caret.
5. If installing the site as a PWA, confirm it opens after installation.

Cloudflare Pages serves the site over HTTPS, which allows the browser to request
microphone permission. The **Dictate** item is hidden when the browser does not
provide speech recognition.

### Troubleshooting

- A `404` at the site root usually means the build output directory is not
  `public` or `index.html` was not uploaded at the top level.
- If a deployment still shows an older version, close existing tabs and reload.
  The service worker may need one navigation to activate its updated cache.
- If dictation is missing, try a browser with Web Speech API support.
- If a custom domain remains pending, verify its nameservers or CNAME record in
  the Pages project's **Custom domains** screen.

## Caddy

To self-host Textarea, install
[Caddy](https://caddyserver.com/docs/install), place this repository on the
server, and point the domain's `A` or `AAAA` DNS record at that server. Ports
`80` and `443` must be reachable from the internet for automatic HTTPS.

The repository's `Caddyfile` serves only `./public`, so files in the repository
root are not web-accessible. Change `textarea.maruel.ca` in that file when
deploying under another domain.

From the repository root, validate the configuration and run Caddy:

```sh
caddy validate --config Caddyfile
caddy run --config Caddyfile
```

The relative document root is resolved from Caddy's working directory. When
using a service manager, set its working directory to the repository root.

Open `https://textarea.maruel.ca` and follow the verification steps from the
Cloudflare Pages section. Caddy obtains and renews the TLS certificate and
redirects HTTP to HTTPS automatically when DNS and network access are correct.

## References

- [Cloudflare Pages Git integration](https://developers.cloudflare.com/pages/get-started/git-integration/)
- [Deploy static HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)
- [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)
- [Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
- [Caddy static files](https://caddyserver.com/docs/quick-starts/static-files)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Running Caddy as a service](https://caddyserver.com/docs/running)
