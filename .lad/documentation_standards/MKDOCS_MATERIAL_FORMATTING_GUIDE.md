# MkDocs Material Formatting Guide for Claude

**Version**: 1.0  
**Date**: 2025-08-17  
**Purpose**: LAD Framework documentation standards to prevent systematic markdown errors in MkDocs Material projects

---

## 🎯 **Essential Quick Reference**

### **❌ Common Errors → ✅ Solutions**

| Error | Correct Solution | Impact |
|-------|------------------|--------|
| `<details>` without `markdown="1"` | `<details markdown="1">` | Enables markdown processing in HTML |
| Missing blank line after headers | Always add blank line before tables/lists | Python Markdown parsing requirement |
| Narrow table columns | CSS: `th:nth-child(1) { width: 25%; }` | Prevents text wrapping issues |
| No language in code blocks | ```` → ```python` | Enables syntax highlighting |

---

## 📋 **Required MkDocs Configuration**

### **Essential Extensions (mkdocs.yml)**

```yaml
markdown_extensions:
  - md_in_html          # ⭐ REQUIRED for <details> tags
  - pymdownx.details    # ⭐ REQUIRED for collapsible sections
  - pymdownx.superfences:  # ⭐ REQUIRED for Mermaid
      custom_fences:
        - name: mermaid
          class: mermaid
          format: !!python/name:pymdownx.superfences.fence_code_format
  - tables
  - toc:
      permalink: true

theme:
  name: material
  features:
    - content.code.copy
    - navigation.sections

extra_css:
  - stylesheets/extra.css  # For table styling fixes
```

---

## 🔧 **Progressive Disclosure (HTML5 Details)**

### **✅ Correct Syntax**

```markdown
<details markdown="1">
<summary>🔧 **Section Title**</summary>

Content with **full markdown support**.

- Lists work properly
- Tables render correctly

```python
def example():
    return "Code highlighting works"
```

</details>
```

### **❌ Common Errors**

```markdown
<!-- WRONG: Missing markdown attribute -->
<details>
<summary>Title</summary>
**This won't be bold**
</details>

<!-- WRONG: No blank line after summary -->
<details markdown="1">
<summary>Title</summary>
Content breaks formatting
```

### **Best Practices**
- **Maximum 2-3 levels**: Users get lost beyond this
- **Essential content always visible**: Advanced content collapsible
- **Clear summaries**: Use descriptive titles with emojis

---

## 📊 **Table Formatting**

### **✅ Critical Requirements**

```markdown
## Header Example

⚠️ **BLANK LINE REQUIRED HERE**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `name` | string | Yes | Model identifier |
| `config` | object | No | Configuration options |
```

### **Responsive Table CSS (extra.css)**

```css
/* Fix narrow Parameter column */
.md-typeset table:not([class]) th:nth-child(1) {
    width: 25%;
    min-width: 140px;
}

.md-typeset table:not([class]) th:nth-child(4) {
    width: 45%;  /* Description column */
}

/* Responsive wrapper */
.md-typeset table:not([class]) {
    table-layout: fixed;
    width: 100%;
}
```

---

## 📝 **Blank Line Rules**

### **Critical Requirements**
1. **After headers**: Before tables, lists, code blocks
2. **Around code blocks**: Before and after
3. **Before details tags**: Proper separation

```markdown
## Header

Blank line required here

| Table | Example |
|-------|---------|
| Data  | Value   |

Another blank line here

<details markdown="1">
<summary>Section</summary>

Content here.

</details>
```

---

## 🎨 **Code Block Standards**

### **✅ Always Specify Language**

```markdown
```python
def process_data():
    return "highlighted"
```

```bash
emuses analyze --input data.csv
```

```yaml
config:
  setting: value
```
```

---

## 🔍 **Automated Validation**

### **Required Tools Setup**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: markdownlint
        name: Lint Markdown
        entry: markdownlint
        language: node
        files: '^docs/.*\.md$'
        additional_dependencies: ['markdownlint-cli']
```

### **Build Validation**

```bash
# Required checks before commit
markdownlint docs/
mkdocs build --strict
```

---

## 🎯 **LAD Integration Instructions**

### **Claude Prompt Enhancement**

Add to system prompts:

> "For MkDocs Material documentation: Reference `/documentation_standards/MKDOCS_MATERIAL_FORMATTING_GUIDE.md` for formatting standards. Key requirements: `markdown="1"` for details tags, blank lines after headers, language-specific code blocks, responsive table CSS."

### **Quality Checklist**

- [ ] `<details>` tags have `markdown="1"`
- [ ] Blank lines after headers before content
- [ ] Code blocks specify language
- [ ] Tables use responsive CSS
- [ ] Progressive disclosure ≤ 3 levels
- [ ] Validation passes: `markdownlint` + `mkdocs build --strict`

---

## 🚨 **Common Troubleshooting**

### **Details Tags Not Rendering**
- **Cause**: Missing `markdown="1"` or `md_in_html` extension
- **Fix**: Add attribute and enable extension

### **Tables Not Formatting**
- **Cause**: No blank line after header
- **Fix**: Always add blank line before tables

### **Build Failures**
- **Cause**: Broken links or invalid syntax
- **Fix**: Use `mkdocs build --strict --verbose` for details

---

## 📋 **Document Structure Template**

```markdown
# Document Title

## **Essential Information** (Always Visible)
Critical content for all users.

<details markdown="1">
<summary>🔧 **Advanced Configuration**</summary>

Power user content here.

</details>

<details markdown="1">
<summary>💻 **Developer Integration**</summary>

Technical details for developers.

</details>
```

---

**🎯 This guide addresses systematic formatting errors and establishes quality standards for MkDocs Material documentation in LAD framework projects.**

---

*LAD Framework Documentation Standards v1.0*  
*Research-based guidelines for error-free technical documentation*