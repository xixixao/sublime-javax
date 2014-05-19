'''
Various code generation for Java.

See README.md for details.

@author: xixixao <xixixao@seznam.cz>
@license: MIT (http://www.opensource.org/licenses/mit-license.php)
@since: 2014-05-03
'''

import sublime
import sublime_plugin
import re
from collections import namedtuple

# Note: klass == class

# Custom data structures
Klass = namedtuple('Klass', 'accessor name')
Field = namedtuple('Field', 'type name')

# Public: Generates an inner class Builder for current top-scope class
#
# This is the well-known Builder Design Pattern, having a setter for each
# instance field of outer class.
class JavaxGenerateBuilderCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        selections = view.sel()
        fileContent = view.substr(sublime.Region(0, view.size()))
        klass = getKlass(fileContent)
        lastSelection = findEndOfLastSelection(view, selections)
        indentSize = inferIndentSize(fileContent)
        selectedText = '\n'.join([view.substr(selection) for selection in selections])
        instanceFields = fieldsIn(selectedText)
        builder = builderDeclaration(klass, instanceFields)
        generatedCode = builder
        contentSize = view.insert(edit, lastSelection,
            formatJava(indentSize, 1, generatedCode))
        view.show_at_center(lastSelection)
        selections.clear()
        selections.add(sublime.Region(lastSelection, lastSelection + contentSize))


class JavaxGenerateConstructorCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        selections = view.sel()
        fileContent = view.substr(sublime.Region(0, view.size()))
        klass = getKlass(fileContent)
        lastSelection = findEndOfLastSelection(view, selections)
        indentSize = inferIndentSize(fileContent)
        selectedText = '\n'.join([view.substr(selection) for selection in selections])
        instanceFields = fieldsIn(selectedText)
        constructor = constructorDeclaration(klass, instanceFields)
        contentSize = view.insert(edit, lastSelection, formatJava(
            indentSize, 1, constructor))
        view.show_at_center(lastSelection)
        selections.clear()
        selections.add(sublime.Region(lastSelection, lastSelection + contentSize))



class JavaxGenerateGettersCommand(sublime_plugin.TextCommand):
    def run(self, edit):
        view = self.view
        selections = view.sel()
        fileContent = view.substr(sublime.Region(0, view.size()))
        lastSelection = findEndOfLastSelection(view, selections)
        indentSize = inferIndentSize(fileContent)
        selectedText = '\n'.join([view.substr(selection) for selection in selections])
        instanceFields = fieldsIn(selectedText)
        getters = gettersDeclaration(instanceFields)
        contentSize = view.insert(edit, lastSelection,
            formatJava(indentSize, 1, getters))
        view.show_at_center(lastSelection)
        selections.clear()
        selections.add(sublime.Region(lastSelection, lastSelection + contentSize))




# Private: return the top level class with name and accessor
def getKlass(text):
    pattern = r"""
        ((?P<accessor>\w+)\s+)?
        class\s+
        (?P<name>\w+)
    """
    found = Klass(**re.search(pattern, text, re.VERBOSE).groupdict())
    return Klass(found.accessor or '', found.name)

# Private: find the position after last newline selected
def findEndOfLastSelection(view, selections):
    return view.lines(selections[-1])[-1].end() + 1;

# Private: infer the indentation step size used in the file, default to 2 spaces
#          We look for first indent after the class's opening brace.
def inferIndentSize(text):
    firstIndentation = re.search(r'\{.*?\n( +)', text, re.DOTALL)
    return len(firstIndentation.group(1) if firstIndentation else '  ')

# Private:
def constructorDeclaration(klass, fields):
    return """\
        private %(klassName)s(%(arguments)s) {
            %(assignments)s
        }
    """ % dict(
        klassName = klass.name,
        arguments = ', '.join(map(variableDeclaration, fields)),
        assignments = '\n'.join(map(assignment, fields))
    )

# Private: returns a list of Fields with types and names
def fieldsIn(text):
    pattern = r"""
        ^\s* # from start of the line, with potential indent
        %(accessor)s
        ((transient|volatile)\s+)?
        (final\s+)?
        (?P<type>[\w$\<\>\,\.\s]+)\s+
        (?P<name>[\w$]+)
        \s*(;|=)
    """ % dict(accessor = ACCESSOR_REGEXP)
    flags = re.MULTILINE | re.VERBOSE
    return [Field(**m.groupdict()) for m in re.finditer(pattern, text, flags)]

# Private: the whole Builder class
def builderDeclaration(klass, fields):
    return """
        %(accessor)s static class Builder {
            %(builderFields)s

            %(setters)s
            %(accessor)s %(klassName)s build() {
                return new %(klassName)s(%(fieldNames)s);
            }
        }
    """ % dict(
        accessor = klass.accessor,
        builderFields = '\n'.join(map(fieldDeclaration, fields)),
        setters = '\n'.join(map(setterDeclaration(klass.accessor), fields)),
        klassName = klass.name,
        fieldNames = ', '.join([field.name for field in fields])
    )

# Private: return a declaration of a Field with private accessor
def fieldDeclaration(field):
    return "private %(variable)s;" % dict(variable = variableDeclaration(field))

# Private: given an accessor, return a function which given a Field
#          will return a setter declaration with that accessor
def setterDeclaration(accessor):
    def fn(field):
        return """\
            %(accessor)s Builder set%(capitalizedName)s(%(parameter)s) {
                %(assignment)s
                return this;
            }
        """ % dict(
            accessor = accessor,
            capitalizedName = capitalize(field.name),
            assignment = assignment(field),
            parameter = variableDeclaration(field)
        )
    return fn

def gettersDeclaration(fields):
    return '\n'.join(map(getterDeclaration('public'), fields))

# Private: given an accessor, return a function which given a Field
#          will return a setter declaration with that accessor
def getterDeclaration(accessor):
    def fn(field):
        return """\
            %(accessor)s %(type)s get%(capitalizedName)s() {
                return %(name)s;
            }
        """ % dict(
            accessor = accessor,
            capitalizedName = capitalize(field.name),
            name = field.name,
            type = field.type
        )
    return fn

# Private: because Python sucks
def capitalize(str):
    return str[:1].upper() + str[1:]

# Private: return an assignment of a Field with a variable of the same
#          name
def assignment(field):
    return "this.%(name)s = %(name)s;" % field._asdict()

# Private: return the simple type name pair used in various declarations of
#          variables
def variableDeclaration(field):
    return "%(type)s %(name)s" % field._asdict()

# Private: reformats the code to have proper indentation
def formatJava(indentSize, initialIndent, code):
    indentLevel = initialIndent
    tokens = re.split(r'([\{\};]?\n)', stripIndentation(code))
    indentedTokens = []
    for token in tokens:
        if len(token) > 0:
            if token == '{\n':
                indentLevel += 1
            elif token == '}\n':
                indentLevel -= 1
            if token not in ('{\n', ';\n', '\n'):
                indentedTokens.append(indentationToken(indentLevel, indentSize))
            indentedTokens.append(token)
    return ''.join(indentedTokens)

# Private: first get rid of the bad indentation
def stripIndentation(code):
    return re.sub('(^|\n) *', '\n', code)

# Private: returns just enough spaces
def indentationToken(indentLevel, indentSize):
    return ''.join(' ' * indentLevel * indentSize)

# Private: any accessor, including package-private
ACCESSOR_REGEXP = r"""
    (
        (   private
        |   protected
        |   public
        )\s+
    )?
"""
