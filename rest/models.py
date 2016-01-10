from django.contrib.contenttypes.models import (
    ContentType as DjangoContentType,
    ContentTypeManager as DjangoContentTypeManager
)
from django.utils.encoding import force_text
from django.utils.six import string_types


class ContentTypeManager(DjangoContentTypeManager):
    def get_by_identifier(self, identifier):
        return self.get(model=identifier)


class ContentType(DjangoContentType):
    objects = ContentTypeManager()

    @property
    def identifier(self):
        return self.model

    @property
    def urlbase(self):
        cls = self.model_class()
        if cls is None:
            return None
        config = self.get_config()
        if config:
            return config['url']
        urlbase = force_text(cls._meta.verbose_name_plural)
        return urlbase.replace(' ', '')

    @property
    def has_geo_fields(self):
        cls = self.model_class()
        for fld in ('latitude', 'longitude', 'geometry'):
            if fld in cls._meta.get_all_field_names():
                return True
        return False

    # Get foreign keys for this content type
    def get_foreign_keys(self):
        cls = self.model_class()
        if cls is None:
            return []
        parents = {}
        for f in cls._meta.fields:
            if f.rel is not None and type(f.rel).__name__ == 'ManyToOneRel':
                parent = get_ct(f.rel.to)
                parents.setdefault(parent, [])
                parents[parent].append(f.name)
        return parents

    def get_parents(self):
        return set(self.get_foreign_keys().keys())

    def get_children(self, include_rels=False):
        cls = self.model_class()
        if cls is None:
            return []
        rels = cls._meta.get_all_related_objects()

        # get_all_related_objects() structure changed in Django 1.8
        def get_model(rel):
            return getattr(rel, 'related_model', rel.model)

        children = [(get_ct(get_model(rel)), rel) for rel in rels]
        if include_rels:
            return set(children)
        else:
            return set(child[0] for child in children)

    def get_config(self, user=None):
        from . import router  # avoid circular import
        cls = self.model_class()
        return router.get_model_config(cls, user)

    def is_registered(self):
        from . import router  # avoid circular import
        cls = self.model_class()
        return router.model_is_registered(cls)

    class Meta:
        proxy = True


def get_ct(model, for_concrete_model=False):
    if isinstance(model, string_types):
        ctype = ContentType.objects.get_by_identifier(model)
    else:
        ctype = ContentType.objects.get_for_model(
            model, for_concrete_model=for_concrete_model
        )
        # get_for_model sometimes returns a DjangoContentType - caching issue?
        if not isinstance(ctype, ContentType):
            ctype = ContentType.objects.get(pk=ctype.pk)
            ContentType.objects._add_to_cache(ContentType.objects.db, ctype)
    return ctype


def get_object_id(instance):
    ct = get_ct(instance)
    config = ct.get_config()
    if config and 'lookup' in config:
        return getattr(instance, config['lookup'])
    return instance.pk


def get_by_identifier(queryset, ident):
    if hasattr(queryset, 'get_by_identifier'):
        return queryset.get_by_identifier(ident)
    else:
        ct = get_ct(queryset.model)
        config = ct.get_config()
        if config and 'lookup' in config:
            lookup = config['lookup']
        else:
            lookup = 'pk'
        return queryset.get(**{lookup: ident})


class MultiQuerySet(object):
    querysets = []

    def __init__(self, *args, **kwargs):
        self.querysets = args

    def __getitem__(self, index):
        if isinstance(index, slice):
            multi = True
        else:
            multi = False
            index = slice(index, index + 1)

        result = []
        for qs in self.querysets:
            if index.start < qs.count():
                result.extend(qs[index])
            index = slice(index.start - qs.count(),
                          index.stop - qs.count())
            if index.start < 0:
                if index.stop < 0:
                    break
                index = slice(0, index.stop)
        if multi:
            return (item for item in result)
        else:
            return result[0]

    def __iter__(self):
        for qs in self.querysets:
            for item in qs:
                yield item

    def count(self):
        result = 0
        for qs in self.querysets:
            result += qs.count()
        return result

    def __len__(self):
        return self.count()
