<system>
You are Claude. Assemble a review bundle for human or GPT reviewer.

**📝 Documentation Standards**: For MkDocs Material projects, follow formatting guidelines in `/documentation_standards/MKDOCS_MATERIAL_FORMATTING_GUIDE.md` when creating documentation - ensure proper table formatting, blank lines after headers, and correct progressive disclosure syntax.
</system>
<user>
Generate `review_{{FEATURE_SLUG}}.md` containing:

1. <100-word feature summary
2. Diff-stat of this branch vs main
3. Key code blocks (+ inline comments)
4. Code quality metrics (flake8 complexity, test coverage %, Radon SLOC/MI if applicable)
5. Tests added / updated (note testing strategy: integration for APIs, unit for business logic)
6. Known limitations or TODOs
7. Links to relevant docs

Output the file contents only.
</user>