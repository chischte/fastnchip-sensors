# Code Quality Guidelines

Follow Clean Code principles for all new and modified code.

- Prefer simple, readable and maintainable solutions over clever ones.
- Keep functions small and focused on one responsibility.
- Use clear, descriptive names for variables, functions, classes and files.
- Avoid duplicated code; extract shared logic when appropriate.
- Avoid unnecessary abstractions and premature optimization.
- Minimize nesting and complex control flow.
- Prefer early returns where they improve readability.
- Keep modules and classes focused on a single responsibility.
- Separate business logic from hardware, I/O, networking and UI code.
- Avoid magic numbers and magic strings; use named constants.
- Do not introduce global mutable state unless unavoidable.
- Handle errors explicitly.
- Remove dead code, unused variables and obsolete comments.
- Comments should explain why, not restate what the code does.
- Preserve existing public interfaces unless changing them is necessary.
- Refactor nearby code when needed to keep the implementation clean.
- Do not over-engineer.
- Before finishing, review the changed code for readability, duplication,
- unnecessary complexity and violations of these principles.
- Keep hardware access, control logic, networking, sensor handling and UI
- separated into clearly defined modules. Avoid blocking code where possible
- and avoid hidden dependencies or global mutable state.