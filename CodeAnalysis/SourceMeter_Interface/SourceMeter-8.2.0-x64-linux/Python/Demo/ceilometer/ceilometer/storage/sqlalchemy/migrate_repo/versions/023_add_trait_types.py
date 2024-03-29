#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
from migrate import ForeignKeyConstraint
from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy import Table
from sqlalchemy import UniqueConstraint

from ceilometer.storage.sqlalchemy import migration


def upgrade(migrate_engine):
    meta = MetaData(migrate_engine)
    trait_type = Table(
        'trait_type', meta,
        Column('id', Integer, primary_key=True),
        Column('desc', String(255)),
        Column('data_type', Integer),
        UniqueConstraint('desc', 'data_type', name="tt_unique"),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )
    trait = Table('trait', meta, autoload=True)
    unique_name = Table('unique_name', meta, autoload=True)
    trait_type.create(migrate_engine)
    # Trait type extracts data from Trait and Unique name.
    # We take all trait names from Unique Name, and data types
    # from Trait. We then remove dtype and name from trait, and
    # remove the name field.

    conn = migrate_engine.connect()
    sql = ("INSERT INTO trait_type "
           "SELECT unique_name.id, unique_name.key, trait.t_type FROM trait "
           "INNER JOIN unique_name "
           "ON trait.name_id = unique_name.id "
           "GROUP BY unique_name.id, unique_name.key, trait.t_type")
    conn.execute(sql)
    conn.close()

    # Now we need to drop the foreign key constraint, rename
    # the trait.name column, and re-add a new foreign
    # key constraint
    params = {'columns': [trait.c.name_id],
              'refcolumns': [unique_name.c.id]}
    if migrate_engine.name == 'mysql':
        params['name'] = "trait_ibfk_1"  # foreign key to the unique name table
    fkey = ForeignKeyConstraint(**params)
    fkey.drop()

    Column('trait_type_id', Integer).create(trait)

    # Move data from name_id column into trait_type_id column
    query = select([trait.c.id, trait.c.name_id])
    for key, value in migration.paged(query):
        (trait.update().where(trait.c.id == key).
         values({"trait_type_id": value}).execute())

    trait.c.name_id.drop()

    params = {'columns': [trait.c.trait_type_id],
              'refcolumns': [trait_type.c.id]}
    if migrate_engine.name == 'mysql':
        params['name'] = "_".join(('fk', 'trait_type', 'id'))

    fkey = ForeignKeyConstraint(**params)
    fkey.create()

    # Drop the t_type column to data_type.
    trait.c.t_type.drop()

    # Finally, drop the unique_name table - we don't need it
    # anymore.
    unique_name.drop()


def downgrade(migrate_engine):
    meta = MetaData(migrate_engine)
    unique_name = Table(
        'unique_name', meta,
        Column('id', Integer, primary_key=True),
        Column('key', String(255), unique=True),
        mysql_engine='InnoDB',
        mysql_charset='utf8',
    )

    trait_type = Table('trait_type', meta, autoload=True)
    trait = Table('trait', meta, autoload=True)

    # Create the UniqueName table, drop the foreign key constraint
    # to trait_type, drop the trait_type table, rename the
    # trait.trait_type column to traitname, re-add the dtype to
    # the trait table, and re-add the old foreign key constraint

    unique_name.create(migrate_engine)

    conn = migrate_engine.connect()
    sql = ("INSERT INTO unique_name "
           "SELECT trait_type.id, trait_type.desc "
           "FROM trait_type")

    conn.execute(sql)
    conn.close()
    params = {'columns': [trait.c.trait_type_id],
              'refcolumns': [trait_type.c.id]}

    if migrate_engine.name == 'mysql':
        params['name'] = "_".join(('fk', 'trait_type', 'id'))
    fkey = ForeignKeyConstraint(**params)
    fkey.drop()

    # Re-create the old columns in trait
    Column("name_id", Integer).create(trait)
    Column("t_type", Integer).create(trait)

    # copy data from trait_type.data_type into trait.t_type
    query = select([trait_type.c.id, trait_type.c.data_type])
    for key, value in migration.paged(query):
        (trait.update().where(trait.c.trait_type_id == key).
         values({"t_type": value}).execute())

    # Move data from name_id column into trait_type_id column
    query = select([trait.c.id, trait.c.trait_type_id])
    for key, value in migration.paged(query):
        (trait.update().where(trait.c.id == key).
         values({"name_id": value}).execute())

    # Add a foreign key to the unique_name table
    params = {'columns': [trait.c.name_id],
              'refcolumns': [unique_name.c.id]}
    if migrate_engine.name == 'mysql':
        params['name'] = 'trait_ibfk_1'
    fkey = ForeignKeyConstraint(**params)
    fkey.create()

    trait.c.trait_type_id.drop()

    # Drop the trait_type table. It isn't needed anymore
    trait_type.drop()
