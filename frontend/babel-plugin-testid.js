// Makes `data-testid` work on EVERY React Native component on web, at compile time.
// React Native Web only forwards data-* props on View/Text; TextInput, TouchableOpacity, Pressable and most
// wrappers drop them, which made half the app untestable. This rewrites
//   <X data-testid="foo" />  ->  <X testID="foo" dataSet={{ testid: "foo" }} />
// on capitalized (React) components only; DOM tags keep the native attribute. Explicit testID / dataSet win.
// Only touches app/ and components/ source, never node_modules.
const nodePath = require('path');

module.exports = function testidPlugin({ types: t }) {
  const inScope = (filename) => {
    if (!filename || filename.includes('node_modules')) return false;
    const rel = nodePath.relative(__dirname, filename);
    return rel.startsWith('app' + nodePath.sep) || rel.startsWith('components' + nodePath.sep);
  };
  const attrName = (a) => (t.isJSXAttribute(a) && a.name ? (t.isJSXNamespacedName(a.name) ? `${a.name.namespace.name}:${a.name.name.name}` : a.name.name) : null);

  return {
    name: 'data-testid-everywhere',
    visitor: {
      JSXOpeningElement(path, state) {
        if (!inScope(state.filename)) return;
        const name = path.node.name;
        const tag = t.isJSXIdentifier(name) ? name.name : t.isJSXMemberExpression(name) ? 'Member' : null;
        if (!tag || !/^[A-Z]/.test(tag)) return;
        const idx = path.node.attributes.findIndex((a) => attrName(a) === 'data-testid');
        if (idx < 0) return;
        let expr = path.node.attributes[idx].value;
        if (t.isJSXExpressionContainer(expr)) expr = expr.expression;
        if (!expr || t.isJSXEmptyExpression(expr)) return;
        path.node.attributes.splice(idx, 1);
        const has = (n) => path.node.attributes.some((a) => attrName(a) === n);
        if (!has('testID')) path.node.attributes.push(t.jsxAttribute(t.jsxIdentifier('testID'), t.jsxExpressionContainer(t.cloneNode(expr))));
        if (!has('dataSet')) {
          path.node.attributes.push(t.jsxAttribute(t.jsxIdentifier('dataSet'),
            t.jsxExpressionContainer(t.objectExpression([t.objectProperty(t.identifier('testid'), t.cloneNode(expr))]))));
        }
      },
    },
  };
};
