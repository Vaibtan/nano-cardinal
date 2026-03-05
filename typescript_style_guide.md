# Google TypeScript Style Guide

> Based on the [official Google TypeScript Style Guide](https://google.github.io/styleguide/tsguide.html).
> Use this document as a reference for Codex, Claude Code, or any AI coding assistant when writing TypeScript.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Source File Basics](#source-file-basics)
3. [Source File Structure](#source-file-structure)
4. [Language Features](#language-features)
   - [Variables](#variables)
   - [Arrays](#arrays)
   - [Objects](#objects)
   - [Classes](#classes)
   - [Functions](#functions)
   - [Type System](#type-system)
   - [Control Structures](#control-structures)
   - [Decorators](#decorators)
   - [Disallowed Features](#disallowed-features)
5. [Comments and JSDoc](#comments-and-jsdoc)
6. [Naming Conventions](#naming-conventions)
7. [Code Formatting](#code-formatting)
8. [Policies](#policies)

---

## Introduction

### Terminology

This guide uses RFC 2119 terminology:

- **must** / **must not** — mandatory rule
- **should** / **should not** (also *prefer* / *avoid*) — strongly recommended
- **may** — permissible option

### Guide Notes

All code examples are **non-normative**: they illustrate the style guide but do not represent the only valid way to write code. Optional formatting choices shown in examples must not be enforced as rules.

---

## Source File Basics

### File Encoding

Source files must be encoded in **UTF-8**.

### Whitespace Characters

Only the ASCII horizontal space character (0x20) may appear as whitespace outside string literals. All other whitespace characters in string literals must be escaped.

### Special Escape Sequences

Use the named escape sequence rather than numeric escapes:

| Use this | Not this |
|---|---|
| `\n` | `\x0a` or `\u000a` |
| `\t` | `\x09` |
| `\'`, `\"`, `\\`, `\b`, `\f`, `\r`, `\v` | numeric equivalents |

Legacy octal escapes (`\012`) are **never** used.

### Non-ASCII Characters

Use the actual Unicode character where possible. Use hex/Unicode escapes only for non-printable characters, always with an explanatory comment.

```typescript
// ✅ Good: clear and readable
const units = 'μs';
const output = '\ufeff' + content; // byte order mark

// ❌ Bad: hard to read
const units = '\u03bcs'; // Greek letter mu, 's'
const output = '\ufeff' + content; // reader has no idea what this is
```

---

## Source File Structure

Files must be ordered as follows, each section separated by **exactly one blank line**:

1. Copyright/license JSDoc (if present)
2. `@fileoverview` JSDoc (if present)
3. Imports (if present)
4. File implementation

### Copyright Information

If a license or copyright notice is needed, add it as a JSDoc block at the very top of the file.

### `@fileoverview` JSDoc

```typescript
/**
 * @fileoverview Description of file. Lorem ipsum dolor sit amet, consectetur
 * adipiscing elit, sed do eiusmod tempor incididunt.
 */
```

Wrapped lines are **not** indented.

### Imports

#### Four Import Variants

| Import type | Syntax | When to use |
|---|---|---|
| Module (namespace) | `import * as foo from '...';` | Large APIs, many symbols |
| Named (destructuring) | `import {SomeThing} from '...';` | Primary TypeScript import style |
| Default | `import SomeThing from '...';` | Only when external code requires it |
| Side-effect | `import '...';` | Only to trigger load-time side effects |

```typescript
// ✅ Good
import * as ng from '@angular/core';
import {Foo} from './foo';
import Button from 'Button'; // only when necessary
import 'jasmine'; // side-effect import
```

#### Import Paths

- Use **relative imports** (`./foo`, `../bar`) for files within the same project.
- Use path-from-root imports (`root/path/to/file`) when needed.
- Limit the number of parent steps (`../../../`) as they make structure hard to understand.

```typescript
// ✅ Good
import {Symbol1} from 'path/from/root';
import {Symbol2} from '../parent/file';
import {Symbol3} from './sibling';
```

#### Namespace vs. Named Imports

- **Prefer named imports** for frequently used symbols with clear names (e.g., Jasmine's `describe`, `it`).
- **Prefer namespace imports** when using many symbols from large APIs to avoid long destructured lists.

```typescript
// ❌ Bad: needlessly long destructured import
import {Item as TableviewItem, Header as TableviewHeader, Row as TableviewRow,
  Model as TableviewModel, Renderer as TableviewRenderer} from './tableview';

// ✅ Good: use namespace import
import * as tableview from './tableview';
let item: tableview.Item | undefined;
```

```typescript
// ❌ Bad: namespace prefix adds no value for common test helpers
import * as testing from './testing';
testing.describe('foo', () => { testing.it('bar', () => {}); });

// ✅ Good: named imports are clearer
import {describe, it, expect} from './testing';
describe('foo', () => { it('bar', () => {}); });
```

#### Renaming Imports

Rename imports (`import {SomeThing as SomeOtherThing}`) only when:
1. Avoiding a name collision with other imports.
2. The imported symbol name is auto-generated.
3. The original name is unclear (e.g., rename RxJS `from` to `observableFrom`).

### Exports

#### Use Named Exports Only

```typescript
// ✅ Good: named export
export class Foo { ... }
export const SOME_CONSTANT = ...;
export function someHelpfulFunction() { ... }

// ❌ Bad: default export
export default class Foo { ... }
```

**Why?** Default exports provide no canonical name, allowing any name at import sites and making refactoring harder.

#### Export Visibility

Only export symbols used outside the module. Minimize the exported API surface.

#### No Mutable Exports (`export let`)

`export let` is **not allowed**. Mutable exports create confusing and hard-to-debug behavior across re-exports.

```typescript
// ❌ Bad
export let foo = 3;

// ✅ Good: use a getter function for mutable state
let foo = 3;
export function getFoo() { return foo; }
```

#### No Container Classes for Namespacing

```typescript
// ❌ Bad: static-only class for namespacing
export class Container {
  static FOO = 1;
  static bar() { return 1; }
}

// ✅ Good: export individual constants and functions
export const FOO = 1;
export function bar() { return 1; }
```

### Import and Export Type

#### `import type`

Use `import type` when a symbol is used only as a type, not at runtime:

```typescript
// ✅ Good
import type {Foo} from './foo';
import {Bar} from './foo';

import {type Foo, Bar} from './foo'; // inline type import also fine
```

Use `import '...';` (no binding) to force a runtime load for side effects.

#### `export type`

Use `export type` when re-exporting a type:

```typescript
// ✅ Good
export type {AnInterface} from './foo';
```

### Use Modules, Not Namespaces

- **Must** use ES6 `import`/`export`.
- **Must not** use `namespace Foo { ... }` (except to interface with third-party code).
- **Must not** use `require()` for imports.
- **Must not** use `/// <reference path="..."/>`.

```typescript
// ❌ Bad
namespace Rocket { function launch() { ... } }
/// <reference path="..."/>
import x = require('mydep');

// ✅ Good
import {foo} from 'bar';
```

---

## Language Features

### Variables

#### Use `const` and `let`, Never `var`

```typescript
const foo = otherValue;   // ✅ default: use const
let bar = someValue;      // ✅ only when reassignment is needed
var baz = someValue;      // ❌ never use var
```

- Variables **must not** be used before their declaration.

#### One Variable Per Declaration

```typescript
// ❌ Bad
let a = 1, b = 2;

// ✅ Good
let a = 1;
let b = 2;
```

---

### Arrays

#### Do Not Use the `Array()` Constructor

```typescript
// ❌ Bad: confusing behavior
const a = new Array(2);    // [undefined, undefined]
const b = new Array(2, 3); // [2, 3]

// ✅ Good
const a = [2];
const b = [2, 3];
const c: number[] = [];
c.length = 2;
Array.from<number>({length: 5}).fill(0); // [0, 0, 0, 0, 0]
```

#### Do Not Define Non-Numeric Properties on Arrays

Use a `Map` or `Object` instead of attaching custom properties to an array.

#### Spread Syntax

Use `[...foo]` for shallow copies and concatenation. Only spread iterables — **never** spread `null`, `undefined`, or primitives.

```typescript
// ❌ Bad
const bar = [5, ...(shouldUseFoo && foo)]; // might spread undefined

// ✅ Good
const foo = shouldUseFoo ? [7] : [];
const bar = [5, ...foo];
```

#### Array Destructuring

```typescript
// ✅ Good
const [a, b, c, ...rest] = generateResults();
let [, b,, d] = someArray; // omit unused elements

// ✅ Good: default value on the left-hand side
function destructured([a = 4, b = 2] = []) { … }

// ❌ Bad: default value on the right-hand side
function badDestructuring([a, b] = [4, 2]) { … }
```

**Tip:** Prefer object destructuring over array destructuring for function parameters/returns when possible, as it allows naming elements.

---

### Objects

#### Do Not Use the `Object()` Constructor

```typescript
// ❌ Bad
const obj = new Object();

// ✅ Good
const obj = {};
const obj2 = {a: 0, b: 1, c: 2};
```

#### Iterating Objects

Do not use unfiltered `for...in`. Use `for...of Object.keys()` or `for...of Object.entries()` instead.

```typescript
// ❌ Bad: includes prototype chain properties
for (const x in someObj) { ... }

// ✅ Good
for (const x in someObj) {
  if (!someObj.hasOwnProperty(x)) continue;
}
for (const x of Object.keys(someObj)) { ... }
for (const [key, value] of Object.entries(someObj)) { ... }
```

#### Object Spread Syntax

Only spread objects into objects. Never spread arrays, primitives, `null`, or `undefined`.

```typescript
// ❌ Bad
const bar = {num: 5, ...(shouldUseFoo && foo)}; // might be undefined
const ids = {...fooStrings}; // spreading an array into an object

// ✅ Good
const foo = shouldUseFoo ? {num: 7} : {};
const bar = {num: 5, ...foo};
```

Later values override earlier values at the same key when spreading.

#### Object Destructuring

Keep destructured function parameters simple: single level, unquoted, shorthand properties only. Specify defaults on the left-hand side.

```typescript
// ✅ Good
interface Options { num?: number; str?: string; }
function destructured({num, str = 'default'}: Options = {}) {}

// ❌ Bad: too deeply nested or non-trivial default
function nestedTooDeeply({x: {num, str}}: {x: Options}) {}
function nontrivialDefault({num, str}: Options = {num: 42, str: 'default'}) {}
```

#### Computed Property Names

Computed keys like `{['key' + foo()]: 42}` are allowed but are treated as dict-style (quoted) keys. Do not mix quoted and unquoted keys unless the computed key is a `Symbol`.

---

### Classes

#### Class Declarations

- Class **declarations** must **not** end with a semicolon.
- Class **expressions** (assigned to a variable) **must** end with a semicolon.

```typescript
// ✅ Good: declaration
class Foo {}

// ✅ Good: expression assigned to variable
export const Baz = class extends Bar {
  method(): number { return this.x; }
};

// ❌ Bad: semicolon on declaration
class Foo {};
```

#### Class Method Declarations

Methods must **not** be separated by semicolons. Methods **should** be separated from each other by a single blank line.

```typescript
// ✅ Good
class Foo {
  doThing() {
    console.log('A');
  }

  getOtherThing(): number {
    return 4;
  }
}
```

#### Constructors

- Always use parentheses when calling `new`, even with no arguments: `new Foo()` not `new Foo`.
- Do **not** provide empty constructors or trivial delegate constructors — ES2015 provides defaults.
- **Exception:** Keep constructors with parameter properties, visibility modifiers, or decorators even if empty.
- Separate the constructor from surrounding class members with one blank line above and below.

```typescript
// ❌ Bad: unnecessary empty constructor
class UnnecessaryConstructor { constructor() {} }

// ✅ Good: parameter property constructor — keep it
class Foo { constructor(private readonly barService: BarService) {} }
```

#### Static Methods

- Prefer module-local functions over private static methods where possible.
- **Must not** call static methods on a subclass that doesn't define them itself.
- **Must not** use `this` inside a static method.

```typescript
// ❌ Bad
class MyClass {
  static foo() {
    return this.staticField; // bad: this in static context
  }
}
Sub.foo(); // bad: calling inherited static on subclass
```

#### Class Members

##### No `#private` Fields

Use TypeScript's `private` keyword instead of JS private identifiers (`#`).

```typescript
// ❌ Bad
class Clazz { #ident = 1; }

// ✅ Good
class Clazz { private ident = 1; }
```

##### Use `readonly`

Mark properties never reassigned outside the constructor with `readonly`.

##### Parameter Properties

Use TypeScript parameter properties instead of manual assignment in the constructor.

```typescript
// ❌ Bad
class Foo {
  private readonly barService: BarService;
  constructor(barService: BarService) { this.barService = barService; }
}

// ✅ Good
class Foo {
  constructor(private readonly barService: BarService) {}
}
```

##### Field Initializers

Initialize class fields at declaration when possible to avoid a constructor.

```typescript
// ❌ Bad
class Foo {
  private readonly userList: string[];
  constructor() { this.userList = []; }
}

// ✅ Good
class Foo {
  private readonly userList: string[] = [];
}
```

##### Visibility Modifiers

- Limit visibility as much as possible.
- TypeScript symbols are `public` by default — **never** add the `public` modifier unless declaring a non-readonly public constructor parameter.
- **Must not** use `obj['foo']` to bypass visibility restrictions.

```typescript
// ❌ Bad
class Foo {
  public bar = new Bar(); // public modifier unnecessary
  constructor(public readonly baz: Baz) {} // readonly implies public
}

// ✅ Good
class Foo {
  bar = new Bar();
  constructor(public baz: Baz) {} // public allowed here
}
```

##### Getters and Setters

- Getters **must** be pure functions — no observable side effects.
- At least one accessor must be non-trivial. Do not define pass-through accessors just to hide a property; make it public or `readonly` instead.
- **Must not** use `Object.defineProperty` for getters/setters (it interferes with property renaming).

```typescript
// ❌ Bad: getter changes state
get next() { return this.nextId++; }

// ✅ Good: pure getter
get someMember(): string { return this.someService.someVariable; }
```

##### Computed Properties in Classes

Only use computed property names in classes when the property is a `Symbol` (e.g., `[Symbol.iterator]`). Use `Symbol` sparingly.

#### Do Not Manipulate Prototypes Directly

Never set or modify `prototype` properties. Do not modify built-in object prototypes.

---

### Functions

#### Prefer Function Declarations for Named Functions

```typescript
// ✅ Good: function declaration
function foo() { return 42; }

// ❌ Avoid: arrow function assigned to const for a named function
const foo = () => 42;
```

Exception: Arrow functions may be used when an explicit type annotation is required on the function.

#### Do Not Use Function Expressions

Use arrow functions instead of `function` expressions.

```typescript
// ✅ Good
bar(() => { this.doSomething(); });

// ❌ Bad
bar(function() { ... });
```

Exception: Use `function` expressions only when code must dynamically rebind `this` or for generator functions.

#### Arrow Function Bodies

- Use **block body** `{ ... }` when the return value is not used (ensures `void` return type).
- Use **concise body** `=>` expression only when the return value is actually used.

```typescript
// ❌ Bad: return value leaks from concise body
myPromise.then(v => console.log(v));

// ✅ Good: block body ensures void
myPromise.then(v => {
  console.log(v);
});

// ✅ Also good: explicit void operator
myPromise.then(v => void console.log(v));

// ✅ Good: concise body when return value is used
const longThings = myValues.filter(v => v.length > 1000).map(v => String(v));
```

#### Rebinding `this`

Function declarations and expressions **must not** use `this` unless specifically rebinding it. Prefer arrow functions or explicit parameters.

```typescript
// ❌ Bad
document.body.onclick = function clickHandler() { this.textContent = 'Hello'; };

// ✅ Good
document.body.onclick = () => { document.body.textContent = 'hello'; };
const setTextFn = (e: HTMLElement) => { e.textContent = 'hello'; };
```

#### Prefer Arrow Functions Over `.bind(this)`, `goog.bind`, or `const self = this`

#### Pass Arrow Functions as Callbacks (Not Named Callbacks Directly)

```typescript
// ❌ Bad: parseInt receives index as radix argument
const numbers = ['11', '5', '10'].map(parseInt);
// Result: [11, NaN, 2]

// ✅ Good: explicit forwarding
const numbers = ['11', '5', '3'].map((n) => parseInt(n));
```

#### Arrow Functions as Class Properties

Classes **should not** contain properties initialized to arrow functions. Manage `this` at the call site.

```typescript
// ❌ Bad: arrow function as property
class DelayHandler {
  private patienceTracker = () => { this.waitedPatiently = true; };
}

// ✅ Good: call the method from an arrow function at the call site
class DelayHandler {
  constructor() {
    setTimeout(() => { this.patienceTracker(); }, 5000);
  }
  private patienceTracker() { this.waitedPatiently = true; }
}
```

#### Parameter Initializers

Optional parameters should have default values using `=`.

```typescript
function process(count: number = 0) { ... }
```

#### Rest Parameters

Use rest parameters (`...args`) instead of `arguments`. Never name a local variable `arguments`.

#### Formatting Function Arguments

If function arguments do not fit on one line:
- Put all args on one line if they fit.
- Put each arg on its own line (one arg per line, trailing comma).

Do not add spaces inside function call parentheses.

---

### Type System

#### Type Inference

- Rely on TypeScript's type inference where possible — do not redundantly annotate obvious types.
- Always annotate function return types and parameter types explicitly.

```typescript
// ❌ Bad: redundant type annotation
const x: boolean = true;

// ✅ Good: let TypeScript infer
const x = true;

// ✅ Always annotate function signatures
function add(a: number, b: number): number { return a + b; }
```

#### `any` Type

- Avoid using `any`. It defeats type safety.
- If `any` must be used, add a comment explaining why.
- Prefer `unknown` over `any` when the type is truly unknown.

```typescript
// ❌ Bad
let value: any = getConfig();

// ✅ Better
let value: unknown = getConfig();
if (typeof value === 'string') { ... }
```

#### `undefined` and `null`

- Use `undefined` to mean "value not set."
- Avoid using `null` unless interoperating with an API that uses it.
- Never initialize optional fields to `null`.

#### Nullable/Optional Types

Use TypeScript's `?` for optional properties and parameters, and union with `| undefined` explicitly when needed.

```typescript
// ✅ Good
interface Config { timeout?: number; }
function greet(name?: string): string { return `Hello, ${name ?? 'world'}`; }
```

#### Type Assertions

- Avoid type assertions (`as Foo` or `<Foo>`). Prefer type narrowing via type guards.
- If assertions are necessary, use the `as` syntax (not angle brackets `<Foo>`), except in `.tsx` files where `as` is mandatory.
- Never use `!` (non-null assertion) unless you are certain the value cannot be null/undefined.

```typescript
// ❌ Bad
const x = getValue() as string;

// ✅ Good: type guard
if (typeof getValue() === 'string') { ... }
```

#### Interfaces vs. Type Aliases

- Use **interfaces** to define object shapes and for things that should be extendable.
- Use **type aliases** for union types, intersection types, and utility types.

```typescript
// ✅ Good: interface for object shapes
interface User { id: number; name: string; }

// ✅ Good: type alias for unions
type StringOrNumber = string | number;
```

#### Generics

- Use descriptive type parameter names (e.g., `TValue`, `TKey`) for complex generics; single letters (`T`, `K`, `V`) are fine for simple cases.
- Do not use `object` — use `Record<string, unknown>` or a specific interface.

#### Enums

- Use `const enum` for performance where possible in non-public APIs.
- Prefer `enum` (PascalCase) for public-facing API enums.
- Do not use string-based numeric enums.

#### Structural Typing

TypeScript uses structural typing. Do not use class instances purely as type containers — prefer interfaces.

#### Mapped and Conditional Types

These are allowed but should be used sparingly and documented clearly.

---

### Control Structures

#### Equality

Always use `===` and `!==` (strict equality). Never use `==` or `!=`.

```typescript
// ❌ Bad
if (value == null) { ... }

// ✅ Good
if (value === null || value === undefined) { ... }
// or
if (value == null) { ... } // acceptable ONLY for null/undefined check shorthand
```

#### `for...of` vs. `for...in`

Prefer `for...of` over `for...in` for iterating arrays and iterables.

```typescript
// ✅ Good
for (const item of items) { ... }

// ❌ Avoid for arrays
for (const i in items) { ... }
```

#### Exceptions

Always throw `Error` objects (or subclasses), never string literals.

```typescript
// ❌ Bad
throw 'Something went wrong';

// ✅ Good
throw new Error('Something went wrong');
```

#### Switch Statements

Every `switch` statement must include a `default` case, even if it only throws an error.

```typescript
switch (foo) {
  case 1:
    doSomething();
    break;
  default:
    throw new Error(`Unexpected value: ${foo}`);
}
```

#### Template Literals

Use template literals instead of string concatenation.

```typescript
// ❌ Bad
const msg = 'Hello, ' + name + '!';

// ✅ Good
const msg = `Hello, ${name}!`;
```

Do not use multi-line string literals with `\` continuation. Use template literals for multi-line strings.

```typescript
// ❌ Bad
const longString = 'This is a very long string that \
    spans multiple lines.';

// ✅ Good
const longString = `This is a very long string that spans multiple lines.`;
```

---

### Decorators

- Decorators (`@Decorator`) should only be used when they are provided by a framework (e.g., Angular, TypeORM) or when there is a compelling reason.
- Do not create decorators in application code.
- Decorators must be placed immediately before the decorated class, method, or property, with no blank lines between the decorator and the decorated item.

---

### Disallowed Features

The following are explicitly **forbidden**:

| Feature | Alternative |
|---|---|
| `var` | `const` or `let` |
| `namespace Foo { }` | ES6 modules |
| `require()` imports | `import` statement |
| `/// <reference path>` | `import` statement |
| `with` statement | Not allowed |
| `eval()` | Not allowed |
| Modifying built-in prototypes | Not allowed |
| `export let` (mutable exports) | Getter functions |
| `Array()` constructor | Array literals |
| `Object()` constructor | Object literals |
| `#private` fields | `private` keyword |
| `Object.defineProperty` for getters/setters | `get`/`set` syntax |
| Function expressions (anonymous `function`) | Arrow functions |
| Default exports | Named exports |
| `this` in static methods | Direct class reference |
| Unfiltered `for...in` on objects | `for...of Object.keys()` |
| `!` non-null assertion without certainty | Type guards |
| Throw non-Error values | `throw new Error(...)` |

---

## Comments and JSDoc

### JSDoc vs. Inline Comments

- Use `/** ... */` JSDoc for all public API symbols (classes, methods, properties, etc.).
- Use `// ...` for implementation comments inside function bodies.
- Do **not** use `/* ... */` block comments for non-JSDoc purposes.

### What to Document

Always document:
- All public symbols (exported functions, classes, interfaces, constants).
- Non-obvious implementation decisions.
- Parameters with `@param`, return types with `@returns`, and thrown errors with `@throws`.

```typescript
/**
 * Fetches a user by ID from the database.
 * @param userId The unique identifier of the user.
 * @returns A promise resolving to the User object.
 * @throws {NotFoundError} If no user with the given ID exists.
 */
async function getUser(userId: string): Promise<User> { ... }
```

### JSDoc Tags

Use standard JSDoc tags:

| Tag | Usage |
|---|---|
| `@param name Description` | Document function parameters |
| `@returns Description` | Document return value |
| `@throws {ErrorType} Description` | Document thrown errors |
| `@deprecated` | Mark deprecated symbols |
| `@see URL` | Reference external documentation |
| `@override` | Mark that a method overrides a parent |
| `@final` | Mark class/method as not extendable |
| `@template T` | Document generic type parameters |
| `@fileoverview` | Top-level file description |

### Parameter Property Comments

When using TypeScript constructor parameter properties, document them with `@param`:

```typescript
class Foo {
  /**
   * @param barService The service used for bar operations.
   */
  constructor(private readonly barService: BarService) {}
}
```

### Comment Style

- Write in complete sentences with proper punctuation.
- Avoid restating the obvious.
- Use third-person singular for method descriptions: *"Returns the user ID"*, not *"Return the user ID"*.
- Do not use `@author` tags.
- Always put a blank line between the JSDoc description and the first tag.

---

## Naming Conventions

| Symbol type | Convention | Example |
|---|---|---|
| Classes, interfaces, enums, type aliases | `UpperCamelCase` | `MyClass`, `UserService` |
| Variables, functions, methods, parameters | `lowerCamelCase` | `myVariable`, `getUserById` |
| Constants (module-level `const`) | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| File names | `lower-kebab-case` or `lower_snake_case` | `my-service.ts` |
| Private class members | `lowerCamelCase` (no underscore prefix) | `private myField` |
| Generic type parameters | `UpperCamelCase` or single uppercase | `T`, `TKey`, `TValue` |
| Enum members | `UPPER_SNAKE_CASE` | `enum Status { ACTIVE, INACTIVE }` |

### Rules

- **Abbreviations:** Treat abbreviations as words — `XmlParser`, not `XMLParser`; `loadHttp`, not `loadHTTP`.
- **No underscores** as prefix or suffix (no `_private`, no `private_`).
- **Descriptive names:** Avoid single-letter names except in loops or short lambdas. `index` is better than `i` in most cases.
- **Boolean names:** Prefer names with `is`, `has`, `can`, `should` prefix: `isEnabled`, `hasChildren`.
- **Do not shadow** outer scope names inside inner scopes.

---

## Code Formatting

### Indentation

Use **2 spaces** for indentation. Do not use tabs.

### Column Limit

Lines should be **at most 80 characters** long. Wrap long lines.

### Semicolons

Always use semicolons to terminate statements. Do not rely on Automatic Semicolon Insertion (ASI).

```typescript
// ✅ Good
const x = 5;
function foo() { return x; }

// ❌ Bad (relies on ASI)
const x = 5
```

### Braces

- Use braces for all control flow bodies, even single-line `if`/`for`/`while`.
- Opening brace goes on the same line as the statement (K&R / Egyptian bracket style).

```typescript
// ✅ Good
if (condition) {
  doSomething();
}

// ❌ Bad
if (condition)
  doSomething();
```

### Line Wrapping

When wrapping an expression across multiple lines:
- Indent continuation lines by **4 spaces** relative to the original line (or align with the opening delimiter).
- Each item in a wrapped list gets its own line with a trailing comma.

```typescript
// ✅ Good: trailing comma on last element
const arr = [
  'first',
  'second',
  'third',
];

// ✅ Good: function call
doSomething(
    argument1,
    argument2,
    argument3,
);
```

### Blank Lines

- Use **one blank line** between top-level definitions (classes, functions).
- Use one blank line between methods in a class.
- Blank lines inside function bodies should be used sparingly.
- No blank line at the start or end of a block.

### Spaces

- Put a space after keywords: `if (`, `for (`, `while (`.
- Put a space before opening brace: `function foo() {`.
- No space before function call parentheses: `foo()` not `foo ()`.
- No space inside parentheses: `foo(bar)` not `foo( bar )`.
- Put spaces around binary operators: `a + b`, `x === y`.
- Put a space after comma: `[a, b, c]`.
- Put a space after colon in type annotations: `x: number`.

### Quotes

Use **single quotes** for strings by default. Use template literals for interpolation or multi-line strings.

```typescript
// ✅ Good
const name = 'Vaibhav';
const msg = `Hello, ${name}`;

// ❌ Avoid double quotes for plain strings
const name = "Vaibhav";
```

### Type Annotations Formatting

- No space before `:` in type annotations in function parameters.
- Space after `:`.
- Use `|` with spaces for union types: `string | number`.
- Place `?` directly after the property/parameter name, before `:`.

```typescript
function process(name: string, value?: number): string | null { ... }
```

### Trailing Commas

Use trailing commas in multi-line lists (arrays, objects, function parameters, type parameters).

```typescript
// ✅ Good
const obj = {
  a: 1,
  b: 2, // trailing comma
};
```

### Parentheses

- Do not use unnecessary parentheses around single arrow function parameters: `x => x * 2` (not `(x) => x * 2`), unless the type is annotated.
- Do use parentheses for clarity with complex expressions.

---

## Policies

### Compatibility

- Compile TypeScript to a target JavaScript version that supports your minimum browser/Node.js version.
- Do not use `Symbol` beyond `Symbol.iterator` unless you can polyfill.
- Avoid ES2015+ features that are not downleveled correctly by the TypeScript compiler for your target.

### Deprecation

- When deprecating a symbol, add `@deprecated` in JSDoc with a description of the replacement.

```typescript
/**
 * @deprecated Use `newFunction()` instead.
 */
export function oldFunction() { ... }
```

### Framework-Specific Rules

- **Angular:** Template properties should use `protected` (not `private`), as templates are outside the class lexical scope.
- **Polymer:** Template properties should use `public`.
- Do not use `obj['foo']` to bypass property visibility regardless of framework.

### Code That Defers Loading

When using dynamic `import()`, be mindful of the additional async boundary. Type-check deferred code correctly.

```typescript
// ✅ Good: dynamic import for code splitting
const module = await import('./heavy-module');
```

### Optimization Compatibility

Code must be written to be compatible with JavaScript optimizers:
- Do not call static methods on variables (only on the class directly).
- Do not use `this` in static methods.
- Do not use `obj['prop']` to access known properties — use dot notation.

---

*Last updated: March 2026. Source: [https://google.github.io/styleguide/tsguide.html](https://google.github.io/styleguide/tsguide.html)*
