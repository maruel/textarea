# Deployment setup

Textarea is a static site. It does not need a build command, server, environment
variables, or API credentials.

## Cloudflare Pages

### Set up from the command line

The setup script connects this Git repository to Cloudflare Pages and can attach
a custom domain. Cloudflare deploys the site immediately and automatically
deploys future pushes. No GitHub Action is needed.

1. In **Workers & Pages**, select **Create application** > **Pages** >
   **Connect to Git**. Install and authorize Cloudflare Pages for this GitHub or
   GitLab repository, then leave the project creation flow. This one-time
   provider authorization cannot be performed with a Cloudflare API token.
2. Open the [Cloudflare API token page](https://dash.cloudflare.com/?to=/:account/api-tokens/create).
3. Choose the **Edit Cloudflare Workers** permission template and add
   **Account > Cloudflare Pages > Edit** permission.
4. Include the account that will own the Pages project.
5. Note the **Account ID** and **API Token** shown by Cloudflare.
6. Run the script in an interactive terminal, passing the non-secret account ID.

The script securely prompts for the token.

```sh
./scripts/setup-cloudflare-pages.py \
  --account-id '<account-id>' \
  --custom-domain textarea.maruel.ca
```

The script reads the repository from the `origin` remote and supports GitHub and
GitLab. Use `--git-remote upstream` if the repository to deploy is on another
remote. The project name defaults to that remote repository's name, `textarea`
here. It identifies the project in Cloudflare and normally produces
`textarea.pages.dev`; Cloudflare may add random characters if that subdomain is
already taken. Use `--project-name textarea-my` to select another name or reuse
an existing Git-integrated project.

Cloudflare also requires a production branch when creating the project. A
deployment carrying that branch name updates the production site; deployments
from other branches become previews. The script first checks the selected
remote's default branch, then whether it has only one remote-tracking branch,
and finally whether there is only one remote-tracking branch across all remotes.
For this repository it infers `main`. If the result is ambiguous, pass an
explicit value:

```sh
./scripts/setup-cloudflare-pages.py \
  --account-id '<account-id>' \
  --production-branch main
```

The script configures no build command and publishes `public`. The custom domain
is optional; omit `--custom-domain` to use only the generated `pages.dev`
address.

An apex domain must be a zone in the same Cloudflare account. If a subdomain
uses an external DNS provider, add a CNAME from that hostname to
`<project-name>.pages.dev` after attaching it to the Pages project. Domain
validation can remain pending until DNS is correct and the site has its first
deployment.

### Automatic deployments

Push `main` to deploy the production site:

```sh
git push origin main
```

Other pushed branches receive preview deployments. An existing Direct Upload
project cannot be converted to Git integration; if the selected name belongs to
one, the script asks you to choose a different project name.

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
- [Cloudflare Pages project API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/methods/create/)
- [Cloudflare Pages custom domain API](https://developers.cloudflare.com/api/resources/pages/subresources/projects/subresources/domains/methods/create/)
- [Deploy static HTML](https://developers.cloudflare.com/pages/framework-guides/deploy-anything/)
- [Direct Upload](https://developers.cloudflare.com/pages/get-started/direct-upload/)
- [Pages custom domains](https://developers.cloudflare.com/pages/configuration/custom-domains/)
- [Caddy static files](https://caddyserver.com/docs/quick-starts/static-files)
- [Caddy automatic HTTPS](https://caddyserver.com/docs/automatic-https)
- [Running Caddy as a service](https://caddyserver.com/docs/running)
