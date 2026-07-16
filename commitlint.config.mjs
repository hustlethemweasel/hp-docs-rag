// Conventional Commits per the project constitution (SPEC §2, item 6).
// Deliberately no `chore`: if a change fits no type, reconsider the change.
export default {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "test", "refactor", "perf", "docs", "build", "ci"],
    ],
  },
};
