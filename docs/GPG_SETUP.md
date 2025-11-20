# GPG Commit Signing Setup

> **Purpose**: Configure GPG signing for verified commits on GitHub.
> Required by branch protection rule "Commits must have verified signatures".

## Quick Setup (5 minutes)

### 1. Generate a GPG key

```bash
gpg --full-generate-key
```

Select:
- Key type: `RSA and RSA`
- Key size: `4096`
- Expiration: `0` (never) or `1y` (1 year)
- Name: Your name
- Email: **Must match your GitHub email**
- Passphrase: Optional (see notes below)

### 2. Get your key ID

```bash
gpg --list-secret-keys --keyid-format=long
```

Output:
```
sec   rsa4096/ABC123DEF456GHI7 2025-11-19 [SC]
      CADD407DA8A889DDF6F17484531760280DB85243
uid                 [ultimate] Your Name <your@email.com>
```

Your key ID is `ABC123DEF456GHI7` (the part after `rsa4096/`).

### 3. Export and add to GitHub

```bash
gpg --armor --export ABC123DEF456GHI7
```

Copy the entire output (including `-----BEGIN PGP PUBLIC KEY BLOCK-----`).

Go to **GitHub → Settings → SSH and GPG keys → New GPG key** and paste it.

### 4. Configure Git

```bash
git config --global user.signingkey ABC123DEF456GHI7
git config --global commit.gpgsign true
```

### 5. Configure GPG agent (for passphrase caching)

```bash
# Add to ~/.gnupg/gpg-agent.conf
echo "default-cache-ttl 28800" >> ~/.gnupg/gpg-agent.conf
echo "max-cache-ttl 28800" >> ~/.gnupg/gpg-agent.conf

# Reload agent
gpgconf --reload gpg-agent
```

This caches your passphrase for 8 hours.

### 6. Set GPG_TTY (REQUIRED for passphrase prompts)

Add to your `~/.bashrc` or `~/.zshrc`:

```bash
export GPG_TTY=$(tty)
```

Then reload:
```bash
source ~/.bashrc  # or source ~/.zshrc
```

**Without this, GPG cannot prompt for your passphrase and signing will fail.**

## Re-signing Existing Commits

If you have unsigned commits that need signing:

```bash
# Re-sign last N commits
git rebase --exec 'git commit --amend --no-edit -S' HEAD~N

# Force push (required after rebase)
git push --force origin <branch>
```

## Passphrase Considerations

### No passphrase
- Zero friction
- Key stored unencrypted on disk
- Acceptable if machine has full-disk encryption

### With passphrase
- Enter once per session (cached by gpg-agent)
- Better protection if machine stolen while unlocked
- **Requires GPG_TTY to be set**

## Troubleshooting

### "gpg failed to sign the data"

1. Check GPG_TTY is set:
   ```bash
   echo $GPG_TTY
   ```
   Should output something like `/dev/pts/0`

2. Reload gpg-agent:
   ```bash
   gpgconf --kill gpg-agent
   gpgconf --launch gpg-agent
   ```

3. Test signing:
   ```bash
   echo "test" | gpg --clearsign
   ```

### "No secret key"

Verify key ID matches:
```bash
gpg --list-secret-keys --keyid-format=long
git config --global user.signingkey
```

### Commits showing "Unverified" on GitHub

- Email in GPG key must match GitHub account email
- GPG public key must be uploaded to GitHub
- Check: GitHub → Settings → SSH and GPG keys

## For Claude Code Users

When using Claude Code, GPG passphrase prompts require an interactive terminal. If signing fails:

1. Background Claude: `Ctrl+Z`
2. Export GPG_TTY: `export GPG_TTY=$(tty)`
3. Run the git command manually
4. Return to Claude: `fg`

---

**Last Updated**: 2025-11-19
