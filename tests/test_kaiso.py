from __future__ import absolute_import

import json

import pytest
from mock import patch

from taal import translation_manager, TranslatableString, Translator
from taal.kaiso.context_managers import (
    TypeTranslationContextManager, AttributeTranslationContextManager)
from taal.kaiso.types import get_context, get_message_id, make_from_obj

from tests.models import (
    CustomFieldsEntity, NoCustomFieldsEntity, Translation,
    create_translation_for_entity, MultipleUniques, InheritedUniques)


def test_kaiso_context_managers(manager, type_heirarchy):
    type_context_manager = TypeTranslationContextManager(manager)
    message_ids = set(type_context_manager.list_message_ids())
    assert message_ids == set(['Entity', 'Animal', 'Fish'])

    attr_context_manager = AttributeTranslationContextManager(manager)
    message_ids = set(attr_context_manager.list_message_ids())
    assert message_ids == set(['["Animal", "id"]', '["Animal", "name"]'])


def test_kaiso_translation_manager(manager, type_heirarchy):
    context_message_id_pairs = set(
        translation_manager.list_contexts_and_message_ids(
            manager=manager))
    assert context_message_id_pairs == set([
        ('taal:kaiso_type', 'Entity'),
        ('taal:kaiso_type', 'Animal'),
        ('taal:kaiso_type', 'Fish'),
        ('taal:kaiso_attr', '["Animal", "id"]'),
        ('taal:kaiso_attr', '["Animal", "name"]'),
    ])


def test_field(manager):
    manager.save(CustomFieldsEntity)
    item = CustomFieldsEntity(id=0, identifier="foo")
    manager.save(item)

    retrieved = manager.get(CustomFieldsEntity, id=0)
    assert retrieved.identifier == "foo"


def test_cant_set_translatable_field_directly(manager):
    manager.save(CustomFieldsEntity)
    item = CustomFieldsEntity(name="foo")
    with pytest.raises(RuntimeError) as excinfo:
        manager.save(item)
    assert excinfo.value.message.startswith(
        "Cannot save directly to translated fields")


def test_load_unexpected_value(bound_manager):
    manager = bound_manager

    manager.save(CustomFieldsEntity)
    item = CustomFieldsEntity(id=1, name="foo")
    with patch('taal.kaiso.TranslatableString.to_primitive') as to_primitive:
        to_primitive.return_value = "invalid-value"
        manager.save(item)

    with pytest.raises(RuntimeError) as excinfo:
        manager.get(CustomFieldsEntity, id=1)
    assert excinfo.value.message.startswith(
        "Unexpected value found in placeholder column")


def test_context_message_id(session, manager):
    manager.save(CustomFieldsEntity)
    item = CustomFieldsEntity(id=0)
    manager.save(item)

    create_translation_for_entity(
        session, manager, 'english', item, 'name', 'English name')
    translation = session.query(Translation).one()
    expected_context = "taal:kaiso_field:CustomFieldsEntity:name"
    expected_message_id = json.dumps([("customfieldsentity", "id", 0)])

    assert translation.context == expected_context
    assert translation.message_id == expected_message_id


def test_message_id_for_multiple_uniques(manager):
    manager.save(MultipleUniques)
    item = MultipleUniques()
    manager.save(item)
    message_id = get_message_id(manager, item)
    expected_message_id = json.dumps([
        ("multipleuniques", "id1", 1),
        ("multipleuniques", "id2", 1),
    ])
    assert message_id == expected_message_id


def test_message_id_for_inherited_uniques(manager):
    manager.save(InheritedUniques)
    item = InheritedUniques()
    manager.save(item)
    message_id = get_message_id(manager, item)
    expected_message_id = json.dumps([
        ("inheriteduniques", "id3", 1),
        ("multipleuniques", "id1", 1),
        ("multipleuniques", "id2", 1),
    ])
    assert message_id == expected_message_id


def test_get_translation(session, manager):
    manager.save(CustomFieldsEntity)
    item = CustomFieldsEntity()
    manager.save(item)

    create_translation_for_entity(
        session, manager, 'english', item, 'name', 'English name')

    context = get_context(manager, item, 'name')
    message_id = get_message_id(manager, item)
    translatable = TranslatableString(
        context=context, message_id=message_id)

    translator = Translator(Translation, session, 'english')
    translated_data = translator.translate(translatable)

    assert translated_data == 'English name'


def test_delete(session_cls, bound_manager):
    manager = bound_manager
    manager.save(CustomFieldsEntity)
    item = CustomFieldsEntity(id=0, name="Name", extra1="", extra2=None)
    manager.save(item)

    # make a fresh session each time
    assert session_cls().query(Translation).count() == 2
    manager.delete(item)
    assert session_cls().query(Translation).count() == 0


def test_delete_no_translations(bound_manager):
    manager = bound_manager
    manager.save(NoCustomFieldsEntity)
    item = NoCustomFieldsEntity(id=0)
    manager.save(item)
    manager.delete(item)


def test_make_from_obj(manager):
    obj = CustomFieldsEntity(id=1)
    translatable = make_from_obj(manager, obj, 'name', 'English name')
    assert translatable.message_id == '[["customfieldsentity", "id", 1]]'
    assert translatable.pending_value == 'English name'
