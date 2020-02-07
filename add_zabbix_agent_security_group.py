import os
import sys

import boto3

zabbix_agent_security_group_names = {
    "production": os.environ["ZABBIX_AGENT_SG_NAME_PROD"],
    "development": os.environ["ZABBIX_AGENT_SG_NAME_DEV"]
}
production_vpc_name = os.environ["PRODUCTION_VPC_NAME"]

ec2_client = boto3.client("ec2")
ec2_resource = boto3.resource("ec2")


def main():
    instance_info, network_interfaces = get_instance_info_and_network_interfaces()
    vpc_names_by_id = get_vpc_names_by_id()
    zabbix_agent_sg_ids_by_name = get_zabbix_security_group_ids_by_names()
    add_zabbix_agent_security_groups_to_all_interfaces(instance_info,
                                                       network_interfaces,
                                                       vpc_names_by_id,
                                                       zabbix_agent_sg_ids_by_name)


def add_zabbix_agent_security_groups_to_all_interfaces(instance_info,
                                                       network_interfaces,
                                                       vpc_names_by_id,
                                                       zabbix_agent_sg_ids_by_name):
    zabbix_agent_sg_id_to_add = (zabbix_agent_sg_ids_by_name[zabbix_agent_security_group_names["production"]]
                                 if vpc_names_by_id[instance_info["VpcId"]] == production_vpc_name
                                 else zabbix_agent_sg_ids_by_name[zabbix_agent_security_group_names["development"]])

    for network_interface in network_interfaces:
        previous_security_groups = [security_group["GroupId"]
                                    for security_group in network_interface["info"]["Groups"]]
        network_interface["resource"].modify_attribute(Groups=[*previous_security_groups,
                                                               zabbix_agent_sg_id_to_add])


def get_zabbix_security_group_ids_by_names():
    security_group_pages = ec2_client.get_paginator('describe_security_groups').paginate()
    security_groups = (security_group
                       for page in security_group_pages
                       for security_group in page["SecurityGroups"])
    zabbix_security_groups = (security_group
                              for security_group in security_groups
                              if "zabbix-agent" in security_group["GroupName"])
    security_group_ids_by_name = {security_group["GroupName"]: security_group["GroupId"]
                                  for security_group in zabbix_security_groups}
    return security_group_ids_by_name


def get_vpc_names_by_id():
    vpc_names_by_id = {vpc["VpcId"]: next(tag["Value"]
                                          for tag in vpc["Tags"]
                                          if tag["Key"] == "Name")
                       for vpc in ec2_client.describe_vpcs()["Vpcs"]}
    return vpc_names_by_id


def get_instance_info_and_network_interfaces():
    instance_id = sys.argv[1]
    instance_info = ec2_client.describe_instances(InstanceIds=[instance_id])["Reservations"][0]["Instances"][0]
    network_interfaces = ({"resource": ec2_resource.NetworkInterface(network_interface["NetworkInterfaceId"]),
                           "info": network_interface}
                          for network_interface in instance_info["NetworkInterfaces"])
    return instance_info, network_interfaces


main()
