# Copyright (c) 2015 Infoblox Inc.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import mock

from neutron.common import constants as n_const
from neutron import context
from neutron.tests.unit import testlib_api

from networking_infoblox.neutron.common import dns
from networking_infoblox.neutron.db import infoblox_db as dbi
from networking_infoblox.tests import base


class DnsControllerTestCase(base.TestCase, testlib_api.SqlTestCase):

    def setUp(self):
        super(DnsControllerTestCase, self).setUp()
        self.neutron_cxt = context.get_admin_context()
        self.test_dns_zone = 'infoblox.com'
        self.ib_cxt = self._get_ib_context()
        self.ib_cxt.context = self.neutron_cxt
        self.test_zone_format = "IPV%s" % self.ib_cxt.subnet['ip_version']
        self.controller = dns.DnsController(self.ib_cxt)
        self.controller.pattern_builder = mock.Mock()
        self.controller.pattern_builder.get_zone_name.return_value = (
            self.test_dns_zone)

    def _get_ib_context(self):
        ib_cxt = mock.Mock()
        ib_cxt.network = {'id': 'network-id',
                          'name': 'test-net-1',
                          'tenant_id': 'network-id'}
        ib_cxt.subnet = {'id': 'subnet-id',
                         'name': 'test-sub-1',
                         'tenant_id': 'tenant-id',
                         'network_id': 'network-id',
                         'cidr': '11.11.1.0/24',
                         'ip_version': 4}
        ib_cxt.mapping.dns_view = 'test-dns-view'
        ib_cxt.grid_config.ns_group = None
        ib_cxt.grid_config.default_domain_name_pattern = self.test_dns_zone
        return ib_cxt

    def test_create_dns_zones_without_ns_group(self):
        self.controller.create_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone,
                grid_primary=None,
                grid_secondaries=None,
                extattrs=None),
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'],
                grid_primary=None,
                prefix=None,
                zone_format=self.test_zone_format,
                extattrs=None)
        ]

    def test_create_dns_zones_with_ns_group(self):
        self.ib_cxt.grid_config.ns_group = 'test-ns-group'
        self.controller.create_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone,
                ns_group=self.ib_cxt.grid_config.ns_group,
                extattrs=None),
            mock.call.create_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'],
                prefix=None,
                zone_format=self.test_zone_format,
                extattrs=None)
        ]

    def test_delete_dns_zones_for_shared_network_view(self):
        self.ib_cxt.mapping.shared = True
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]

    def test_delete_dns_zones_for_external_network(self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = True
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]

    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_shared_network(self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = True
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert not dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_shared_network_with_admin_network_deletable(
            self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = True
        self.ib_cxt.grid_config.admin_network_deletion = True

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_static_zone(self):
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = True

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'is_last_subnet_in_private_networks', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_subnet_pattern(self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{subnet_name}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert not dbi.is_last_subnet_in_private_networks.called

    @mock.patch.object(dbi, 'is_last_subnet_in_network', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_network_pattern(self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{network_id}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_network.called

    @mock.patch.object(dbi, 'is_last_subnet_in_tenant', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_tenant_pattern(self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{tenant_name}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_tenant.called

    @mock.patch.object(dbi, 'is_last_subnet_in_address_scope', mock.Mock())
    def test_delete_dns_zones_for_private_network_with_address_scope_pattern(
            self):
        self.ib_cxt.grid_config.default_domain_name_pattern = (
            '{address_scope_id}.infoblox.com')
        self.ib_cxt.mapping.shared = False
        self.ib_cxt.network['router:external'] = False
        self.ib_cxt.network['shared'] = False
        self.ib_cxt.grid_config.admin_network_deletion = False

        self.controller.delete_dns_zones()

        assert self.ib_cxt.ibom.method_calls == [
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.test_dns_zone),
            mock.call.delete_dns_zone(
                self.ib_cxt.mapping.dns_view,
                self.ib_cxt.subnet['cidr'])
        ]
        assert dbi.is_last_subnet_in_address_scope.called

    def test_bind_names(self):
        ip_address = '11.11.1.2'
        hostname = 'test-vm'
        port_id = 'port-id'
        device_owner = n_const.DEVICE_OWNER_DHCP
        self.controller.pattern_builder.get_hostname.return_value = hostname
        fqdn = str.format("{}.{}", hostname, self.test_dns_zone)

        self.controller.bind_names(ip_address, hostname, port_id,
                                   device_owner=None)
        assert self.ib_cxt.ip_alloc.method_calls == []

        self.controller.bind_names(ip_address, hostname, port_id,
                                   device_owner=device_owner)
        assert self.ib_cxt.ip_alloc.method_calls == [
            mock.call.bind_names(mock.ANY,
                                 self.ib_cxt.mapping.dns_view,
                                 ip_address,
                                 fqdn,
                                 None)
        ]

    def test_unbind_names(self):
        ip_address = '11.11.1.2'
        hostname = 'test-vm'
        port_id = 'port-id'
        device_owner = n_const.DEVICE_OWNER_DHCP
        self.controller.pattern_builder.get_hostname.return_value = hostname
        fqdn = str.format("{}.{}", hostname, self.test_dns_zone)

        self.controller.unbind_names(ip_address, hostname, port_id,
                                     device_owner=None)
        assert self.ib_cxt.ip_alloc.method_calls == []

        self.controller.unbind_names(ip_address, hostname, port_id,
                                     device_owner=device_owner)
        assert self.ib_cxt.ip_alloc.method_calls == [
            mock.call.unbind_names(mock.ANY,
                                   self.ib_cxt.mapping.dns_view,
                                   ip_address,
                                   fqdn,
                                   None)
        ]