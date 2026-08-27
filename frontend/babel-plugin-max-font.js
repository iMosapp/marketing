// Injects maxFontSizeMultiplier into every <Text> and <TextInput> at compile
// time so iOS Dynamic Type (large system font) can't blow up layouts.
// Explicit per-element props and spreads still win (we insert first).
module.exports = function maxFontPlugin({ types: t }) {
  const TARGETS = new Set(['Text', 'TextInput']);
  return {
    name: 'max-font-size-multiplier',
    visitor: {
      JSXOpeningElement(path) {
        const name = path.node.name;
        let match = false;
        if (t.isJSXIdentifier(name) && TARGETS.has(name.name)) match = true;
        if (t.isJSXMemberExpression(name) && t.isJSXIdentifier(name.property) && TARGETS.has(name.property.name)) match = true;
        if (!match) return;
        const has = path.node.attributes.some(
          (a) => t.isJSXAttribute(a) && a.name && a.name.name === 'maxFontSizeMultiplier'
        );
        if (has) return;
        path.node.attributes.unshift(
          t.jsxAttribute(t.jsxIdentifier('maxFontSizeMultiplier'), t.jsxExpressionContainer(t.numericLiteral(1)))
        );
      },
    },
  };
};
