// Every react-native <Modal> keeps its form above the iPhone keyboard at compile time: the modal's children are wrapped in
// <ModalKeyboardWrap> (an iOS KeyboardAvoidingView, a no-op elsewhere) unless the modal already avoids the keyboard itself
// (a KeyboardAvoidingView / KeyboardAwareScrollView anywhere inside it). Only touches app/ and components/ source.
const nodePath = require('path');

const AVOIDERS = new Set(['KeyboardAvoidingView', 'KeyboardAwareScrollView', 'ModalKeyboardWrap']);
const WRAP_MODULE = nodePath.resolve(__dirname, 'components/common/ModalKeyboardWrap');

module.exports = function modalKeyboardPlugin({ types: t }) {
  const elName = (name) => {
    if (t.isJSXIdentifier(name)) return name.name;
    if (t.isJSXMemberExpression(name) && t.isJSXIdentifier(name.property)) return name.property.name;
    return null;
  };
  const inScope = (filename) => {
    if (!filename || filename.includes('node_modules')) return false;
    if (filename.startsWith(WRAP_MODULE)) return false;
    const rel = nodePath.relative(__dirname, filename);
    return rel.startsWith('app' + nodePath.sep) || rel.startsWith('components' + nodePath.sep);
  };
  const containsAvoider = (node) => {
    let found = false;
    t.traverseFast(node, (n) => { if (t.isJSXOpeningElement(n) && AVOIDERS.has(elName(n.name))) found = true; });
    return found;
  };

  return {
    name: 'modal-keyboard-avoid',
    visitor: {
      Program: {
        enter(programPath, state) {
          state.mkNeedsImport = false;
          state.mkModalLocal = null;
          for (const s of programPath.node.body) {
            if (!t.isImportDeclaration(s) || s.source.value !== 'react-native') continue;
            for (const sp of s.specifiers) if (t.isImportSpecifier(sp) && t.isIdentifier(sp.imported) && sp.imported.name === 'Modal') state.mkModalLocal = sp.local.name;
          }
        },
        exit(programPath, state) {
          if (!state.mkNeedsImport) return;
          let rel = nodePath.relative(nodePath.dirname(state.filename), WRAP_MODULE).split(nodePath.sep).join('/');
          if (!rel.startsWith('.')) rel = './' + rel;
          programPath.unshiftContainer('body', t.importDeclaration(
            [t.importSpecifier(t.identifier('ModalKeyboardWrap'), t.identifier('ModalKeyboardWrap'))], t.stringLiteral(rel)));
        },
      },
      JSXElement(path, state) {
        if (!state.mkModalLocal || !inScope(state.filename)) return;
        const node = path.node;
        if (elName(node.openingElement.name) !== state.mkModalLocal || node.openingElement.selfClosing || node.__mkWrapped) return;
        const kids = node.children.filter((c) => !(t.isJSXText(c) && !c.value.trim()));
        if (!kids.length || kids.some(containsAvoider)) return;
        node.__mkWrapped = true;
        node.children = [t.jsxElement(t.jsxOpeningElement(t.jsxIdentifier('ModalKeyboardWrap'), []), t.jsxClosingElement(t.jsxIdentifier('ModalKeyboardWrap')), node.children, false)];
        state.mkNeedsImport = true;
      },
    },
  };
};
