// Makes the keyboard dismissible everywhere at compile time (iOS never gives users a way otherwise):
//  * ScrollView / FlatList / SectionList (vertical) -> keyboardDismissMode="on-drag" so a swipe pushes the keyboard down
//  * single-line <TextInput> -> returnKeyType="done" (also gives number/phone pads their native Done toolbar)
//  * multiline <TextInput> -> wrapped in <KeyboardDoneWrap> which adds an iOS "Done" bar above the keyboard
// Explicit props always win. Only touches app/ and components/ source, never node_modules.
const nodePath = require('path');

const SCROLLERS = new Set(['ScrollView', 'FlatList', 'SectionList', 'KeyboardAwareScrollView', 'BottomSheetScrollView']);
const WRAP_MODULE = nodePath.resolve(__dirname, 'components/common/KeyboardDoneWrap');

module.exports = function keyboardPlugin({ types: t }) {
  const elName = (name) => {
    if (t.isJSXIdentifier(name)) return name.name;
    if (t.isJSXMemberExpression(name) && t.isJSXIdentifier(name.property)) return name.property.name;
    return null;
  };
  const attr = (node, n) => node.attributes.find((a) => t.isJSXAttribute(a) && a.name && a.name.name === n);
  const isMultiline = (opening) => {
    const m = attr(opening, 'multiline');
    if (!m) return false;
    if (m.value && t.isJSXExpressionContainer(m.value) && t.isBooleanLiteral(m.value.expression) && m.value.expression.value === false) return false;
    return true;
  };
  const inScope = (filename) => {
    if (!filename || filename.includes('node_modules')) return false;
    if (filename.startsWith(WRAP_MODULE)) return false;
    const rel = nodePath.relative(__dirname, filename);
    return rel.startsWith('app' + nodePath.sep) || rel.startsWith('components' + nodePath.sep);
  };
  const strAttr = (name, value) => t.jsxAttribute(t.jsxIdentifier(name), t.stringLiteral(value));

  return {
    name: 'keyboard-dismiss-everywhere',
    visitor: {
      Program: {
        enter(_, state) { state.kbNeedsImport = false; },
        exit(programPath, state) {
          if (!state.kbNeedsImport) return;
          let rel = nodePath.relative(nodePath.dirname(state.filename), WRAP_MODULE).split(nodePath.sep).join('/');
          if (!rel.startsWith('.')) rel = './' + rel;
          programPath.unshiftContainer('body', t.importDeclaration(
            [t.importSpecifier(t.identifier('KeyboardDoneWrap'), t.identifier('KeyboardDoneWrap'))], t.stringLiteral(rel)));
        },
      },
      JSXOpeningElement(path, state) {
        if (!inScope(state.filename)) return;
        const name = elName(path.node.name);
        if (SCROLLERS.has(name)) {
          if (!attr(path.node, 'keyboardDismissMode') && !attr(path.node, 'horizontal')) path.node.attributes.unshift(strAttr('keyboardDismissMode', 'on-drag'));
          return;
        }
        if (name === 'TextInput' && !isMultiline(path.node) && !attr(path.node, 'returnKeyType')) {
          path.node.attributes.unshift(strAttr('returnKeyType', 'done'));
        }
      },
      JSXElement(path, state) {
        if (!inScope(state.filename)) return;
        const opening = path.node.openingElement;
        if (elName(opening.name) !== 'TextInput' || !isMultiline(opening) || attr(opening, 'inputAccessoryViewID') || path.node.__kbWrapped) return;
        path.node.__kbWrapped = true;
        const idName = path.scope.generateUidIdentifier('kbId');
        opening.attributes.unshift(t.jsxAttribute(t.jsxIdentifier('inputAccessoryViewID'), t.jsxExpressionContainer(idName)));
        const wrapperAttrs = [t.jsxAttribute(t.jsxIdentifier('render'), t.jsxExpressionContainer(t.arrowFunctionExpression([idName], path.node)))];
        const keyAttr = attr(opening, 'key');
        if (keyAttr) {
          wrapperAttrs.push(t.jsxAttribute(t.jsxIdentifier('key'), keyAttr.value));
          opening.attributes = opening.attributes.filter((a) => a !== keyAttr);
        }
        path.replaceWith(t.jsxElement(t.jsxOpeningElement(t.jsxIdentifier('KeyboardDoneWrap'), wrapperAttrs, true), null, [], true));
        state.kbNeedsImport = true;
      },
    },
  };
};
