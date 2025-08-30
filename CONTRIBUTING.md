# Contributing to HOMEPOT Client

Thank you for your interest in contributing to the HOMEPOT Client project. This document provides guidelines for consortium members contributing to this private repository.

## Project Access

This repository is private and restricted to HOMEPOT consortium members only. Please ensure you have proper authorization before contributing.

## Getting Started

1. **Repository Access**: Ensure you have been added to the HOMEPOT project team on GitHub
2. **Clone the Repository**:
   ```bash
   git clone https://github.com/brunel-opensim/homepot-client.git
   cd homepot-client
   ```
3. **Development Setup**: Follow the setup instructions in the main README.md

## Development Workflow

### Branch Protection Policy

> **Important**: The HOMEPOT consortium follows strict branch protection policies to ensure code quality and security. These policies are enforced through process and CI/CD workflows.

**Main Branch Protection Rules:**
- **No direct pushes to `main`** - All changes must go through pull requests
- **Require 2+ reviewer approvals** for all pull requests to main
- **All CI/CD checks must pass** (tests, security scans, code quality)
- **Conversations must be resolved** before merging
- **Branches must be up-to-date** before merging
- **Linear git history** required (no merge commits)

### Branching Strategy

We follow a Git Flow branching model:

- `main`: Production-ready code
- `develop`: Integration branch for features
- `feature/*`: Feature development branches
- `release/*`: Release preparation branches
- `hotfix/*`: Critical bug fixes

### Creating a Feature Branch

```bash
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name
```

### Commit Guidelines

We follow a strict commit message protocol to maintain project history clarity and enable automated tools.

#### Format
```
<type>(<scope>): <description> [#issue]
```

#### Types
- `feat`: New feature
- `fix`: Bug fix  
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build, etc.)
- `security`: Security-related changes
- `ci`: CI/CD changes

#### Scope (optional)
- `client`: Core client functionality
- `cli`: Command line interface
- `api`: API-related changes
- `docs`: Documentation
- `tests`: Test-related
- `workflows`: GitHub Actions/CI

#### Issue References
- `Fixes #123` - Closes the issue
- `Refs #123` - References but doesn't close
- `Closes #123` - Alternative to "Fixes"

#### Rules
1. **One line only** (max 72 characters)
2. **Present tense** ("add" not "added")
3. **No period** at the end
4. **Reference issues** when applicable
5. **Descriptive but concise**

#### Examples
```
feat(client): add device connection management
fix(cli): resolve version display formatting Fixes #42
docs: update installation instructions
test(client): add async connection tests Refs #15
chore: rename requirements file for clarity
security(auth): implement token validation Closes #89
```

### Pull Request Process

1. Ensure your branch is up to date with `develop`
2. Create a pull request targeting `develop` (or `main` for releases)
3. Include a clear description of changes
4. Reference any related issues
5. Ensure all CI/CD checks pass
6. Request review from at least **2 consortium members**
7. Address review feedback promptly
8. **All conversations must be resolved** before merging

> **Direct Push Protection**: If you accidentally try to push directly to main, our CI/CD workflow will block it and provide instructions on creating a proper pull request.

### Repository Access Levels

**Admin (Consortium Leads):**
- Full repository access and settings management
- Can approve and merge pull requests
- Emergency hotfix authority

**Maintainer (Senior Developers):**
- Can approve pull requests (2+ approvals required)
- Can merge to develop branch
- Cannot bypass protection policies

**Write (Active Contributors):**
- Can create feature branches and submit pull requests
- Cannot merge to protected branches
- Standard development access

**Read (Observers/New Members):**
- Can view code and documentation
- Can create issues and participate in discussions
- Learning and onboarding access

## Code Standards

### Code Quality

- Follow language-specific style guides
- Maintain test coverage above 80%
- Use meaningful variable and function names
- Comment complex logic appropriately

### Security Considerations

- Never commit sensitive data (credentials, keys, etc.)
- Use environment variables for configuration
- Follow secure coding practices
- Report security issues privately to project maintainers

## Testing

- Write unit tests for new features
- Ensure integration tests pass
- Test cross-platform compatibility where applicable
- Document test scenarios

## Documentation

- Update documentation for new features
- Include inline code documentation
- Update API documentation as needed
- Maintain changelog entries

## Issue Reporting

When reporting issues:
1. Use the provided issue templates
2. Include detailed reproduction steps
3. Provide environment information
4. Attach relevant logs or screenshots

## Communication

- Use GitHub Discussions for general questions
- Use GitHub Issues for bug reports and feature requests
- Tag relevant team members for urgent matters
- Respect consortium confidentiality agreements

## Compliance

- Ensure contributions comply with consortium agreements
- Respect intellectual property guidelines
- Follow data protection regulations
- Maintain audit trails for compliance purposes

## Contact

For questions about contributing, contact the project maintainers through GitHub or consortium communication channels.

## Review System Test

This section was added to test the branch protection review requirements. The review system should now require 1 reviewer before merging to main.

---

*This project is part of the HOMEPOT consortium and subject to consortium agreements and confidentiality requirements.*
