---
description: "Comprehensive workflow to fetch best practices, antipatterns, and rules for the current tech stack"
---

# 🎯 Fetch Rules Workflow

This workflow analyzes the current tech stack, fetches best practices from multiple sources, consolidates knowledge, and creates project-specific coding rules.

## Phase 1: Stack Analysis 📊

### Step 1.1: Analyze Current Tech Stack
```bash
# Check package dependencies
cat pyproject.toml | grep -A 50 "dependencies"
cat Makefile | grep -E "(PYTHON|pip|test|lint|format)"
cat Dockerfile | grep -E "(FROM|RUN|COPY)"
```

**Current Stack Identified:**
- **Core Python**: 3.11+ (pyyaml, requests)
- **MCP Framework**: mcp, fastmcp
- **Testing**: pytest, pytest-asyncio, pytest-mock, pytest-cov
- **Code Quality**: mypy, black, ruff
- **Container**: Docker/Podman
- **Build Tools**: setuptools, make
- **Async**: uvloop, asyncio
- **Git Operations**: Custom git_utils module

## Phase 2: Documentation Fetching 📚

### Step 2.1: Fetch Context7 Documentation
For each major library, fetch comprehensive documentation:

#### Core Libraries:
- @context7 PyYAML - YAML processing best practices
- @context7 requests - HTTP client patterns and security
- @context7 setuptools - Python packaging standards

#### MCP Framework:
- @context7 mcp - Model Context Protocol implementation
- @context7 fastmcp - FastMCP server development

#### Testing Framework:
- @context7 pytest - Testing patterns and fixtures
- @context7 pytest-asyncio - Async testing strategies
- @context7 pytest-mock - Mocking best practices

#### Code Quality Tools:
- @context7 mypy - Type annotation guidelines
- @context7 black - Code formatting standards
- @context7 ruff - Linting rules and configuration

#### Async Programming:
- @context7 asyncio - Async/await patterns
- @context7 uvloop - Performance optimization

### Step 2.2: Fetch Documentation for Each Component
Execute Context7 queries systematically:

```
@context7 /pytest - focus on "async testing patterns and fixtures"
@context7 /pyyaml - focus on "security and performance best practices"
@context7 /requests - focus on "security, error handling, and performance"
@context7 /mcp - focus on "server development and best practices"
@context7 /fastmcp - focus on "implementation patterns and optimization"
@context7 /mypy - focus on "type annotation patterns and strict mode"
@context7 /black - focus on "configuration and integration"
@context7 /ruff - focus on "rule selection and performance"
@context7 /asyncio - focus on "patterns, pitfalls, and performance"
@context7 /setuptools - focus on "packaging best practices"
```

## Phase 3: Expert Knowledge Gathering 🧠

### Step 3.1: Perplexity Queries for Expert Insights
Use @perplexity_ask for specialized knowledge:

#### Python Async Patterns:
```
@perplexity_ask: "What are the most critical async/await best practices, common pitfalls, and performance optimization techniques for Python 3.11+ applications? Include specific guidance for pytest-asyncio testing, uvloop integration, and concurrent programming patterns."
```

#### MCP Server Development:
```
@perplexity_ask: "What are the best practices, antipatterns, and security considerations for developing Model Context Protocol (MCP) servers using Python? Include guidance on FastMCP, server architecture, and performance optimization."
```

#### Container Optimization:
```
@perplexity_ask: "What are the best practices for Dockerizing Python applications with focus on security, performance, and multi-stage builds? Include specific guidance for Python 3.11+, dependency management, and production deployment."
```

#### Testing Strategies:
```
@perplexity_ask: "What are the most effective testing strategies for Python applications using pytest, pytest-asyncio, and pytest-mock? Include guidance on test organization, fixtures, async testing patterns, and CI/CD integration."
```

#### Code Quality Enforcement:
```
@perplexity_ask: "What are the best practices for Python code quality using mypy, black, and ruff? Include configuration recommendations, integration with CI/CD, and strategies for gradual adoption in existing codebases."
```

## Phase 4: Knowledge Consolidation 🔄

### Step 4.1: Group by Similarity
Organize collected information into categories:

1. **Async Programming Rules**
2. **Testing and Quality Assurance Rules**  
3. **MCP Development Rules**
4. **Container and Deployment Rules**
5. **Code Style and Type Safety Rules**
6. **Security and Performance Rules**
7. **Build and CI/CD Rules**

### Step 4.2: Remove Redundancies
- Identify duplicate recommendations across sources
- Consolidate similar advice into single, comprehensive rules
- Prioritize official documentation over third-party opinions

### Step 4.3: Resolve Contradictions
For conflicting advice, use @web search to verify:

```
@web search: "mypy strict mode vs gradual typing Python 2024"
@web search: "pytest-asyncio auto mode vs strict mode best practices"
@web search: "FastMCP vs standard MCP implementation performance"
```

### Step 4.4: Create Distinct Rules
Transform consolidated knowledge into actionable, specific rules with:
- Clear do/don't statements
- Code examples where applicable
- Rationale for each rule
- Tools/checks to enforce the rule

## Phase 5: Rule Organization and Storage 💾

### Step 5.1: Create Rule Categories
Create structured rule files in `.windsurf/rules/`:

- `async-programming.md` - Async/await patterns and pitfalls
- `testing-standards.md` - pytest and async testing rules
- `mcp-development.md` - MCP server development guidelines
- `container-practices.md` - Docker and deployment rules
- `code-quality.md` - mypy, black, ruff configuration and usage
- `security-guidelines.md` - Security best practices
- `performance-optimization.md` - Performance rules and patterns
- `ci-cd-standards.md` - Build and deployment pipeline rules

### Step 5.2: Rule Format Template
Each rule should follow this format:

```markdown
## Rule: [Rule Name]

**Category**: [Category]
**Severity**: [Critical/Important/Recommended]
**Tools**: [Enforcement tools]

### Description
[Clear description of the rule]

### Rationale
[Why this rule exists]

### Good Example
```python
[Good code example]
```

### Bad Example  
```python
[Bad code example]
```

### Enforcement
[How to check/enforce this rule]

### Related Rules
[Links to related rules]
```

## Phase 6: Execution and Validation ✅

### Step 6.1: Execute Workflow
1. Run all Context7 queries and collect documentation
2. Execute all Perplexity queries and gather expert insights
3. Perform web searches to resolve any contradictions
4. Consolidate all information following the categorization
5. Create the structured rule files

### Step 6.2: Validation
- Review each rule for clarity and actionability
- Ensure no contradictions between rules
- Verify all rules are relevant to the current tech stack
- Test rule enforcement mechanisms where applicable

### Step 6.3: Integration
- Update project documentation to reference rules
- Configure tools (mypy, ruff, etc.) based on established rules
- Create pre-commit hooks for automatic rule enforcement
- Document the rule maintenance process

## Success Criteria ✨

- [ ] Complete tech stack analysis documented
- [ ] Context7 documentation fetched for all major libraries
- [ ] Perplexity expert insights gathered for all key areas
- [ ] All contradictions resolved with web verification
- [ ] Structured rule files created in `.windsurf/rules/`
- [ ] Rules are actionable and enforceable
- [ ] No redundancies between rule categories
- [ ] Integration path documented for team adoption

---

**Note**: This workflow is designed to be executed in phases. Each phase should be completed before moving to the next to ensure comprehensive coverage and quality consolidation of the gathered knowledge. 