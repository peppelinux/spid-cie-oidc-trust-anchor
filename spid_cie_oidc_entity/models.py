from django.db import models
from django.utils.translation import gettext as _
from django.utils import timezone

from spid_cie_oidc_entity.abstract_models import TimeStampedModel
from spid_cie_oidc_entity.jwks import (
    create_jwk,
    serialize_rsa_key,
    private_pem_from_jwk,
    public_pem_from_jwk
)
from cryptojwt.jwk.jwk import key_from_jwk_dict

import datetime
import json
import uuid


class FederationEntityConfiguration(TimeStampedModel):
    """
        Federation Authority configuration.
    """

    def _create_jwks():
        return [create_jwk()]
    
    uuid = models.UUIDField(
        blank=False, null=False, default=uuid.uuid4, unique=True,
        editable=False
    )
    sub = models.URLField(
        max_length=255,
        blank=False,
        null=False,
        help_text=_(
            "URL that identifies this Entity in the Federation. "
            "This value and iss are the same in the Entity Configuration."
        ),
    )
    default_exp = models.PositiveIntegerField(
        default=33,
        help_text=_(
            "how many minutes from now() an issued statement must expire"
        )
    )
    default_signature_alg = models.CharField(
        max_length=16,
        default="RS256",
        blank=False,
        null=False,
        help_text=_("default signature algorithm, eg: RS256"),
    )
    authority_hints = models.JSONField(
        blank=True,
        null=False,
        help_text=_("only required if this Entity is an intermediary"),
        default=list,
    )
    jwks = models.JSONField(
        blank=False,
        null=False,
        help_text=_("a list of public keys"),
        default=_create_jwks,
    )
    trust_marks = models.JSONField(
        blank=True,
        help_text=_(
            "which trust marks MUST be exposed in its entity configuration"
        ),
        default=list,
    )
    trust_marks_issuers = models.JSONField(
        blank=True,
        help_text=_(
            "which issuers are allowed to issue trust marks for the descendants. "
            'Example: {"https://www.spid.gov.it/certification/rp": '
            '["https://registry.spid.agid.gov.it", "https://intermediary.spid.it"],'
            '"https://sgd.aa.it/onboarding": ["https://sgd.aa.it", ]}'
        ),
        default=dict,
    )
    entity_metadatas = models.JSONField(
        blank=False,
        null=False,
        help_text=_(
            'federation_entity metadata, eg: '
            '{"federation_entity": { ... },'
            '"openid_provider": { ... },'
            '"openid_relying_party": { ... },'
            '"oauth_resource": { ... }'
            '}'
        ),
        default=dict,
    )
    http_timeout = models.PositiveIntegerField(
        default=5, help_text=_("in seconds")
    )
    verify_https_cert = models.BooleanField(default=True)

    is_active = models.BooleanField(
        default=False, help_text=_(
            "If this configuration is active. "
            "At least one configuration must be active"
        )
    )

    class Meta:
        verbose_name = "Federation Entity Configuration"
        verbose_name_plural = "Federation Entity Configurations"


    @staticmethod
    def get_active_conf():
        """
        returns the first available active acsia engine configuration found
        """
        return AcsiaConfiguration.objects.filter(is_active=True).first()

    @property
    def public_jwks(self):
        res = []
        for i in self.jwks:
            res.append(
                serialize_rsa_key(
                    key_from_jwk_dict(i).public_key()
                )
            )
        return res

    @property
    def pems(self):
        res = {}
        for i in self.jwks:
            res[i["kid"]] = {
                "public": private_pem_from_jwk(i),
                "private": public_pem_from_jwk(i)
            }
        return json.dumps(res, indent=2)

    @property
    def kids(self):
        return [i['kid'] for i in self.jwks]
    
    @property
    def entity_configuration(self):
        _now = timezone.localtime()
        conf = {
          "exp": int((_now + datetime.timedelta(minutes = self.default_exp)).timestamp()),
          "iat": int(_now.timestamp()),
          "iss": self.sub,
          "sub": self.sub,
          "jwks": self.public_jwks,
          "metadata": self.entity_metadatas
        }

        if self.trust_marks_issuers:
            conf['trust_marks_issuers'] = self.trust_marks_issuers
        
        return json.dumps(conf, indent=2)
    
    def __str__(self):
        return "{} [{}]".format(
            self.sub, "active" if self.is_active else "--"
        )
