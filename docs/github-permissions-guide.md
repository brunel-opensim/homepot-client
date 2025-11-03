# Repository Permission Levels Guide

## GitHub Repository Permissions Overview

GitHub provides several permission levels for repository collaborators. Here's what each level allows:

### 1. **Read** (Most Restrictive)
**What they can do:**
- View repository content
- Clone the repository
- Download releases
- Open issues
- Comment on issues and pull requests
- Fork the repository (if public)
- Create pull requests from forks

**What they CANNOT do:**
- Push commits directly
- Create branches in your repository
- Merge pull requests
- Modify repository settings
- Delete anything

**Best for:** External contributors, community members, auditors

### 2. **Triage** 
**What they can do (includes Read permissions plus):**
- Manage issues and pull requests without write access
- Apply/dismiss labels
- Close/reopen issues and pull requests
- Mark issues as duplicates
- Request pull request reviews

**Best for:** Issue managers, community moderators (rarely used for code repos)

### 3. **Write** (Most Common for Team Members)
**What they can do (includes Read + Triage plus):**
- Push commits to repository
- Create and delete branches
- Create, edit, and delete tags and releases
- Open, close, and comment on issues and pull requests
- Merge pull requests (if branch protection allows)
- Edit and delete comments
- Enable/disable GitHub Pages

**What they CANNOT do:**
- Delete the repository
- Change repository settings
- Manage access permissions
- Force push to protected branches (if configured)

**Best for:** Your 2 core team members

### 4. **Maintain**
**What they can do (includes Write permissions plus):**
- Manage repository settings (some)
- Manage issues and pull requests
- Manage some repository settings like GitHub Pages, webhooks
- Cannot delete repository or transfer ownership

**Best for:** Senior team members, project leads (probably not needed for your team size)

### 5. **Admin** (Most Permissive)
**What they can do (includes all permissions):**
- Delete the repository
- Change repository visibility (public/private)
- Manage collaborators and permissions
- Transfer repository ownership
- Configure branch protection rules
- Manage security settings

**Best for:** You (repository owner)

## Recommended Permission Strategy for Your Team

### Your Current Team (3 people total)

```
You (Repository Owner):     Admin
Core Developer 1:           Write  
Core Developer 2:           Write
```

### External Collaborators

#### Option 1: Fork-based Contributions (Recommended)
```
External Contributors:      No direct access (they fork)
```

**How it works:**
1. External contributors fork your repository
2. They make changes in their fork
3. They submit pull requests from their fork
4. You review and merge (or they can merge if you allow it)

**Advantages:**
- Maximum security - no access to your main repository
- Full audit trail of all changes
- Contributors can work independently
- No risk of accidental damage to main repository

#### Option 2: Direct Access (Use with caution)
```
Trusted External Contributors:  Read (PR only)
```

**When to use:**
- Long-term trusted contributors
- Company partners or contractors
- When you want faster iteration

### Practical Examples

#### For Platform Specialists (External)

**Scenario:** You want an iOS developer to implement APNs support

**Option A - Fork-based (Recommended):**
```bash
# iOS developer process:
1. Fork brunel-opensim/homepot-client
2. Clone their fork: git clone https://github.com/ios-dev/homepot-client.git
3. Create branch: git checkout -b feature/apns-ios
4. Implement APNs provider
5. Push to their fork
6. Create PR from their fork to your main repo
7. You review and merge
```

**Option B - Direct access:**
```bash
# Add them as Read collaborator
# They can create PR branches directly in your repo
1. git clone https://github.com/brunel-opensim/homepot-client.git
2. git checkout -b feature/apns-ios
3. Implement and push
4. Create PR
5. You review and merge
```

## Setting Up Permissions

### In GitHub Web Interface:

1. **Go to Repository Settings**
   - Navigate to your repository
   - Click "Settings" tab
   - Click "Collaborators and teams" (left sidebar)

2. **Add Collaborators**
   ```
   For Core Team Members:
   - Click "Add people"
   - Enter GitHub username
   - Select "Write" permission
   - Send invitation
   ```

3. **Configure Branch Protection** (Recommended)
   ```
   Settings > Branches > Add rule for "main":
   - Require pull request reviews before merging
   - Require status checks to pass before merging
   - Restrict pushes that create files larger than 100MB
   - Allow force pushes (keep disabled)
   - Allow deletions (keep disabled)
   ```

### Using GitHub CLI (Alternative):

```bash
# Add collaborator with Write access
gh api repos/brunel-opensim/homepot-client/collaborators/username \
    --method PUT \
    --field permission='push'

# Add collaborator with Read access  
gh api repos/brunel-opensim/homepot-client/collaborators/username \
    --method PUT \
    --field permission='pull'
```

## Security Best Practices

### For External Contributors:

1. **Always use Fork-based workflow** for unknown contributors
2. **Review all external PRs carefully** - check for:
   - Malicious code
   - Credential leaks
   - Unnecessary permission requests
   - Code quality and testing

3. **Use CODEOWNERS file** to require your approval:
   ```
   # In .github/CODEOWNERS
   * @mghorbani
   /backend/src/homepot/push_notifications/ @mghorbani
   ```

4. **Enable security features:**
   - Dependency scanning
   - Secret scanning
   - Code scanning (if available)

### For Your Core Team:

1. **Give Write access** to trusted team members
2. **Use branch protection** to prevent direct pushes to main
3. **Require PR reviews** even for team members (optional but recommended)
4. **Use descriptive commit messages** and PR descriptions

## Monitoring and Auditing

### Track Repository Activity:
- Repository "Insights" > "Traffic" - see who's accessing
- Repository "Insights" > "Network" - see branch/fork activity  
- Repository "Insights" > "Contributors" - see who's contributing

### Audit Permissions:
- Regularly review collaborator list
- Remove inactive collaborators
- Monitor for suspicious activity

## Recommended Setup for Your Project

```yaml
Repository: brunel-opensim/homepot-client
Owner: You (Admin)

Core Team Access:
  - developer1: Write
  - developer2: Write

External Contributors:
  - Method: Fork-based contributions
  - Permission: None (they fork)
  - Review Process: You approve all external PRs

Branch Protection:
  - main: Protected
  - Require: 1 review for external PRs
  - Require: Status checks pass
  - No force pushes
  - No direct pushes to main
```

This setup gives you maximum control while allowing efficient collaboration with your core team and safe contributions from external developers.
