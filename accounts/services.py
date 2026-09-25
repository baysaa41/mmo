# accounts/services.py

import pandas as pd
import numpy as np
import re

from django_pandas.io import read_frame

# --- Pandas Dataframe Service ---

def generate_styled_user_dataframe_html(users_queryset, is_staff=False):
    """
    Given a queryset of users, generates a styled HTML table using Pandas.
    This keeps the complex Pandas logic out of the view.
    """
    if is_staff:
        fieldnames = ['id', 'username', 'last_name', 'first_name', 'data__province__name',
                      'data__school__name', 'data__grade__name', 'data__reg_num', 'data__mobile', 'email']
        rename_map = {
            'id': 'ID', 'first_name': 'Нэр', 'last_name': 'Овог', 'username': 'Хэрэглэгчийн нэр',
            'data__province__name': 'Аймаг/Дүүрэг', 'data__school__name': 'Cургууль', 'data__grade__name': 'Анги',
            'data__reg_num': 'Регистрын дугаар', 'data__mobile': 'Гар утас', 'email': 'И-мэйл'
        }
    else:
        fieldnames = ['id', 'username', 'last_name', 'first_name', 'data__province__name',
                      'data__school__name', 'data__grade__name']
        rename_map = {
            'id': 'ID', 'first_name': 'Нэр', 'last_name': 'Овог', 'username': 'Хэрэглэгчийн нэр',
            'data__province__name': 'Аймаг/Дүүрэг', 'data__school__name': 'Cургууль', 'data__grade__name': 'Анги'
        }

    pd.options.display.float_format = '{:,.0f}'.format
    users_df = read_frame(users_queryset, fieldnames=fieldnames, verbose=False)
    if 'data__mobile' in users_df.columns:
        users_df['data__mobile'] = users_df['data__mobile'].astype(pd.Int64Dtype())

    users_df.rename(columns=rename_map, inplace=True)
    users_df.index = np.arange(1, len(users_df) + 1)

    styled_df = users_df.style.set_table_attributes('class="table table-bordered table-hover"').set_table_styles([
        {'selector': 'th', 'props': [('text-align', 'center')]},
        {'selector': 'td, th', 'props': [('border', '1px solid #ccc'), ('padding', '3px 5px')]},
    ])

    html_table = styled_df.to_html(na_rep="", escape=False)
    return re.sub('<th class="blank level0" >&nbsp;</th>', '<th class="blank level0" >№</th>', html_table)
