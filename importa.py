import mysql.connector
from mysql.connector import Error
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# conector e base de dados
def connect_to_mariadb():

    # layt
    st.set_page_config(page_title="Inspeções Dinâmicas Dolp",page_icon="🦺", initial_sidebar_state="expanded")
    try:
        # Conectando ao MariaDB
        connection = mysql.connector.connect(
            host='sgddolp.com',
            database='dolpenge_views',
            user='dolpenge_dolpviews',
            password='EuL7(s%MA4)fUZ,l0U'
        )

        if connection.is_connected():
            cursor = connection.cursor()

            # Executando a consulta para pegar os dados de blitz, turnos e pessoas
            query = """
            SELECT b.nome_inspetor, b.num_operacional, b.idtb_turnos, b.data_blitz, t.nom_fant, t.unidade, p.funcao, p.nome
            FROM view_power_bi_blitz_contatos b
            JOIN view_power_bi_turnos t ON b.idtb_turnos = t.idtb_turnos
            JOIN view_power_bi_turnos_pessoas p ON b.idtb_turnos = p.idtb_turnos
            """
            cursor.execute(query)
            resultados = cursor.fetchall()


            # Criando um DataFrame com os dados de blitz
            df = pd.DataFrame(resultados,
                              columns=["nome_inspetor", "num_operacional", "idtb_turnos", "data_blitz", "nom_fant", "unidade", "funcao", "nome"])


            # Convertendo a coluna data_blitz para datetime
            df['data_blitz'] = pd.to_datetime(df['data_blitz'])

            # Filtros na barra lateral
            st.sidebar.header("Filtros")
            ano_selecionado = st.sidebar.selectbox("Ano", df['data_blitz'].dt.year.unique(), index=0)
            mes_selecionado = st.sidebar.selectbox("Mês", df[df['data_blitz'].dt.year == ano_selecionado][
                'data_blitz'].dt.month.unique(), index=0)
            empresas_unicas = df['nom_fant'].unique()
            empresa_selecionada = st.sidebar.selectbox("Selecione a Empresa", empresas_unicas, index=0)
            unidades_unicas = df[df['nom_fant'] == empresa_selecionada]['unidade'].unique()

            # Alteração para multiselect nas unidades
            unidades_selecionadas = st.sidebar.multiselect(
                "Selecione as Unidades",
                unidades_unicas,
                default=unidades_unicas  # Pode definir como todas as unidades selecionadas inicialmente
            )
            # Barra lateral para seleção de página
            grafico_selecionado = st.sidebar.selectbox("Selecione o Gráfico", [
                "Quantidade de Blitz por Instrutor",
                "Quantidade de Inspeção por Equipe",
                "Taxa de Contato",
                "Não Conformidades Apontadas",
                "Integrantes Equipes"

            ])
            instrutores_unicos = df[(df['nom_fant'] == empresa_selecionada) & (df['unidade'].isin(unidades_selecionadas))]['nome_inspetor'].unique()
            instrutores_selecionados = st.sidebar.multiselect("Selecione os Instrutores", instrutores_unicos,
                                                              default=instrutores_unicos)

            # Filtrando os dados com base nas unidades selecionadas
            df_filtrado = df[
                (df['data_blitz'].dt.year == ano_selecionado) &
                (df['data_blitz'].dt.month == mes_selecionado) &
                (df['nom_fant'] == empresa_selecionada) &
                (df['unidade'].isin(unidades_selecionadas)) &
                (df['nome_inspetor'].isin(instrutores_selecionados))
            ]

            # Consulta para pegar os dados de turnos
            query_turnos = f"""
            SELECT t.num_operacional, t.dt_inicio
            FROM view_power_bi_turnos t
            WHERE t.dt_inicio BETWEEN '{ano_selecionado}-{mes_selecionado:02d}-01' AND '{ano_selecionado}-{mes_selecionado:02d}-31'
              AND t.nom_fant = '{empresa_selecionada}'
              AND t.unidade IN ({', '.join(f"'{unidade}'" for unidade in unidades_selecionadas)})
            """
            cursor.execute(query_turnos)
            resultados_turnos = cursor.fetchall()
            df_turnos = pd.DataFrame(resultados_turnos, columns=["num_operacional", "dt_inicio"])

            # Cálculos das equipes para gráficos
            equipes_com_turnos = df_turnos['num_operacional'].unique()
            equipes_inspecionadas = df_filtrado['num_operacional'].unique()
            equipes_inspecionadas_no_turno = set(equipes_inspecionadas).intersection(set(equipes_com_turnos))
            equipes_nao_inspecionadas_no_turno = set(equipes_com_turnos).difference(set(equipes_inspecionadas))

            # Adicionando a consulta para obter os dados das respostas
            query_respostas = f"""
            SELECT r.Key, r.resposta_int, r.pergunta, b.nome_inspetor, b.num_operacional, b.idtb_turnos
            FROM view_power_bi_blitz_respostas r
            JOIN view_power_bi_blitz_contatos b ON r.Key = b.Key
            JOIN view_power_bi_turnos t ON b.idtb_turnos = t.idtb_turnos
            WHERE r.resposta_int = 2
            AND t.nom_fant = '{empresa_selecionada}' 
            AND t.unidade IN ({', '.join(f"'{unidade}'" for unidade in unidades_selecionadas)})
            AND b.data_blitz BETWEEN '{ano_selecionado}-{mes_selecionado:02d}-01' AND '{ano_selecionado}-{mes_selecionado:02d}-31'
            """
            cursor.execute(query_respostas)
            resultados_respostas = cursor.fetchall()

            # Criando DataFrame para as não conformidades
            df_respostas = pd.DataFrame(resultados_respostas,
                                        columns=["Key", "resposta_int", "pergunta", "nome_inspetor", "num_operacional", "idtb_turnos"])

            # Filtrando as respostas com resposta_int = 2
            df_respostas_filtradas = df_respostas[df_respostas['resposta_int'] == 2]

            # Agregando os dados para o gráfico de "Não Conformidades Apontadas Pelas Inspeções"
            nao_conformidade_total = len(df_respostas_filtradas)
            conformidade_total = len(df_filtrado) - nao_conformidade_total

            # Exibição do dashboard--------------------------------------

#--------------------------------------------------------------------------------------------------------------------------------
            st.title("Dashboard Inspeções Dinâmicas")

            # Grafico de Quantidade de Blitz Por Instrutor -------------------------------------------------------------

            if grafico_selecionado == "Quantidade de Blitz por Instrutor":
                blitz_por_instrutor = df_filtrado.groupby("nome_inspetor").agg(
                    quantidade_blitz=('idtb_turnos', 'nunique')).reset_index()
                fig1, ax1 = plt.subplots(figsize=(12, 8))
                sns.barplot(y='nome_inspetor', x='quantidade_blitz', data=blitz_por_instrutor, palette='viridis',
                            ax=ax1)
                ax1.set_title(f'Quantidade de Blitz por Instrutor - {mes_selecionado}/{ano_selecionado}', fontsize=16,
                              fontweight='bold')
                ax1.set_xlabel('')
                ax1.set_ylabel('')
                for i, v in enumerate(blitz_por_instrutor['quantidade_blitz']):
                    ax1.text(v + 0.1, i, f'{v}', ha='left', va='center', fontsize=12, color="black")
                st.pyplot(fig1)
#--------------------------------------------------------------------------------------------------------------------------------

            # Grafico Quatidade de Inspeção Por Equipes -----------------------------------------------
            elif grafico_selecionado == "Quantidade de Inspeção por Equipe":
                blitz_por_equipe = df_filtrado.groupby("num_operacional").agg(
                    quantidade_inspecao=('idtb_turnos', 'nunique')).reset_index()
                fig2, ax2 = plt.subplots(figsize=(12, 8))
                sns.barplot(y='num_operacional', x='quantidade_inspecao', data=blitz_por_equipe, palette='viridis',
                            ax=ax2)
                ax2.set_title(f'Quantidade de Inspeção por Equipe - {mes_selecionado}/{ano_selecionado}', fontsize=16,
                              fontweight='bold')
                ax2.set_xlabel('')
                ax2.set_ylabel('')
                for i, v in enumerate(blitz_por_equipe['quantidade_inspecao']):
                    ax2.text(v + 0.1, i, f'{v}', ha='left', va='center', fontsize=12, color="black")
                st.pyplot(fig2)

#--------------------------------------------------------------------------------------------------------------------------------------
            # Grafico Taxa de Contato -----------------------------------------------
            elif grafico_selecionado == "Taxa de Contato":

                st.subheader(f'Taxa de Contato - {mes_selecionado}/{ano_selecionado}')

                # Gráfico de pizza de equipes inspecionadas

                labels = ['Inspecionadas', 'Não Inspecionadas']

                sizes = [len(equipes_inspecionadas_no_turno), len(equipes_nao_inspecionadas_no_turno)]

                colors = ['#2ca02c', '#d62728']

                explode = (0.1, 0)  # Destaque no primeiro pedaço

                fig3, ax3 = plt.subplots()

                ax3.pie(sizes, explode=explode, labels=labels, colors=colors, autopct='%1.1f%%', shadow=True,

                        startangle=140)

                ax3.axis('equal')  # Assegura que o gráfico será desenhado como um círculo

                st.pyplot(fig3)

                # Linha de separação após o gráfico de pizza

                st.markdown("<hr>", unsafe_allow_html=True)

                # Exibindo as equipes de forma mais agradável

                st.subheader("Equipes Inspecionadas e Não Inspecionadas")

                # Estilo para os cartões

                estilo_bilhetes = """

                    <style>

                    .card {

                        background-color: #F4E1D2;  /* Cor de fundo tipo bilhete */

                        padding: 20px;

                        margin-bottom: 10px;

                        border-radius: 10px;

                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);

                        position: relative;

                        width: 250px;  /* Largura fixa */

                        display: inline-block;

                    }

                    .circle {

                        width: 20px;

                        height: 20px;

                        border-radius: 50%;

                        position: absolute;

                        top: 10px;

                        right: 10px;

                        border: 2px solid white;

                    }

                    .inspecionado {

                        background-color: #D0F0C0;  /* Cor verde claro para inspecionados */

                    }

                    .nao_inspecionado {

                        background-color: #F4CCCC;  /* Cor vermelha claro para não inspecionados */

                    }

                    </style>

                """

                st.markdown(estilo_bilhetes, unsafe_allow_html=True)

                # Criando as colunas para exibir as equipes

                col1, col2 = st.columns(2)

                # Exibindo as equipes inspecionadas

                with col1:

                    st.markdown("### Equipes Inspecionadas")

                    for equipe in equipes_inspecionadas_no_turno:
                        st.markdown(f'<div class="card inspecionado">'

                                    f'<strong>Equipe🛻 {equipe}</strong>'

                                    f'</div>', unsafe_allow_html=True)

                # Exibindo as equipes não inspecionadas

                with col2:

                    st.markdown("### Equipes Não Inspecionadas")

                    for equipe in equipes_nao_inspecionadas_no_turno:
                        st.markdown(f'<div class="card nao_inspecionado">'

                                    f'<strong>Equipe🛻 {equipe}</strong>'

                                    f'</div>', unsafe_allow_html=True)

                # Linha de separação entre as seções

                st.markdown("<hr>", unsafe_allow_html=True)

                # Se houver outros indicadores (como não conformidade, perguntas reprovadas)

                # Adicione os gráficos ou informações adicionais aqui

                # Exemplo de gráficos de não conformidade por inspetor e perguntas reprovadas

                # Esses gráficos podem ser adicionados conforme a necessidade


#----------------------------------------------------------------------------------------------------------------------------
                # Gráfico de pizza para "Não Conformidades Apontadas Pelas Inspeções-----------------------"

            elif grafico_selecionado == "Não Conformidades Apontadas":

                # Gráfico de pizza para "Não Conformidades Apontadas Pelas Inspeções"

                # Quantidade de equipes inspecionadas e equipes com não conformidade (garantindo que sejam únicas)

                equipes_inspecionadas = len(equipes_inspecionadas_no_turno)

                # Considerando apenas as equipes únicas que tiveram não conformidade

                equipes_com_nao_conformidade_unicas = df_respostas_filtradas['num_operacional'].nunique()

                # Calculando a porcentagem

                porcentagem_nao_conformidade = (

               equipes_com_nao_conformidade_unicas / equipes_inspecionadas) * 100 if equipes_inspecionadas > 0 else 0

                porcentagem_conformidade = 100 - porcentagem_nao_conformidade

                # Conformidades e Não conformidades

                conformidades = ['Conforme', 'Não Conforme']

                quantidades = [equipes_inspecionadas - equipes_com_nao_conformidade_unicas,

                               equipes_com_nao_conformidade_unicas]

                # Definindo as cores

                colors = ['#1f77b4', '#ff7f0e']

                # Explodindo a primeira fatia (destaque)

                explode = (0.1, 0)

                # Gerando o gráfico de pizza

                fig4, ax4 = plt.subplots()

                # Função para formatar o texto nas fatias (quantidade + porcentagem)

                def mostrar_quantidade_e_porcentagem(pct, allvals):

                    absolute = int(pct / 100. * sum(allvals))  # Calcula a quantidade real

                    return f"{absolute} ({pct:.1f}%)"

                # Plotando o gráfico de pizza

                ax4.pie(quantidades, explode=explode, labels=conformidades, colors=colors,

                        autopct=lambda pct: mostrar_quantidade_e_porcentagem(pct, quantidades), shadow=True,

                        startangle=90)

                ax4.axis('equal')  # Torna o gráfico circular

                # Adicionando o título centralizado

                ax4.set_title('Não Conformidades Apontadas Pelas Inspeções', fontsize=14, fontweight='bold',

                              loc='center')

                # Exibindo o gráfico

                st.pyplot(fig4)

                # Linha de separação após o gráfico

                st.markdown("<hr>", unsafe_allow_html=True)

                # Indicadores de Não Conformidade por Inspetor

                import random

                # Função para gerar uma cor suave em formato hexadecimal

                def gerar_cor_suave():

                    # Gerar cores em tons suaves (usando valores mais baixos de RGB para cores mais claras)

                    r = random.randint(200, 255)

                    g = random.randint(200, 255)

                    b = random.randint(200, 255)

                    return f"#{r:02x}{g:02x}{b:02x}"

                # Agrupando as não conformidades por inspetor

                nao_conformidade_por_inspetor = df_respostas_filtradas.groupby('nome_inspetor').size().reset_index(

                    name='quantidade')

                # Criando um dicionário para mapear cada inspetor a uma cor única e suave

                cores_inspetores = {inspetor: gerar_cor_suave() for inspetor in

                                    nao_conformidade_por_inspetor['nome_inspetor']}

                # Estilo para os cartões

                estilo_cartoes = """

                <style>

                .card {

                    color: #000000;  /* Cor do texto preta */

                    padding: 20px;

                    margin-bottom: 10px;

                    border-radius: 10px;

                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);

                }

                </style>

                """

                st.markdown(estilo_cartoes, unsafe_allow_html=True)

                # Título dos indicadores

                st.markdown("<h3 style='text-align: center;'>Indicadores de Não Conformidade por Inspetor</h3>",

                            unsafe_allow_html=True)

                # Dividindo os cartões entre duas colunas

                col1, col2 = st.columns(2)

                # Dividindo os dados em duas metades

                metade = len(nao_conformidade_por_inspetor) // 2

                # Primeira metade dos cartões na primeira coluna

                with col1:

                    for index, row in nao_conformidade_por_inspetor.iloc[:metade].iterrows():
                        cor_inspetor = cores_inspetores[row['nome_inspetor']]  # Cor específica para o inspetor

                        st.markdown(f'<div class="card" style="background-color: {cor_inspetor};">'

                                    f"<strong>Inspetor:</strong> {row['nome_inspetor']}<br>"

                                    f"<strong>Quantidade de Não Conformidades:</strong> {row['quantidade']}"

                                    f"</div>", unsafe_allow_html=True)

                # Segunda metade dos cartões na segunda coluna

                with col2:

                    for index, row in nao_conformidade_por_inspetor.iloc[metade:].iterrows():
                        cor_inspetor = cores_inspetores[row['nome_inspetor']]  # Cor específica para o inspetor

                        st.markdown(f'<div class="card" style="background-color: {cor_inspetor};">'

                                    f"<strong>Inspetor:</strong> {row['nome_inspetor']}<br>"

                                    f"<strong>Quantidade de Não Conformidades:</strong> {row['quantidade']}"

                                    f"</div>", unsafe_allow_html=True)

                # Linha de separação após os indicadores de "Não Conformidade por Inspetor"

                st.markdown("<hr>", unsafe_allow_html=True)

                # Exibindo a tabela de perguntas reprovadas em cartões

                st.subheader("Perguntas Reprovadas")

                # Agrupar por equipe, pergunta e nome do inspetor

                tabela_perguntas = df_respostas_filtradas.groupby(

                    ['num_operacional', 'pergunta', 'nome_inspetor']

                ).size().reset_index(name='quantidade')

                # Estilo para os cartões

                estilo_cartoes = """

                <style>

                .card {

                    color: #000000;  /* Cor do texto preta */

                    padding: 20px;

                    margin-bottom: 10px;

                    border-radius: 10px;

                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);

                }

                </style>

                """

                st.markdown(estilo_cartoes, unsafe_allow_html=True)

                # Dividindo os cartões entre duas colunas

                col1, col2 = st.columns(2)

                # Dividindo a tabela em duas metades

                metade = len(tabela_perguntas) // 2

                # Primeira metade das perguntas reprovadas na primeira coluna

                with col1:

                    for index, row in tabela_perguntas.iloc[:metade].iterrows():
                        cor_inspetor = cores_inspetores[row['nome_inspetor']]  # Cor específica para o inspetor

                        st.markdown(f'<div class="card" style="background-color: {cor_inspetor};">'

                                    f"<strong>Equipe🛻 {row['num_operacional']}</strong><br>"

                                    f"<strong>Pergunta:</strong> {row['pergunta']}<br>"

                                    f"<strong>Inspetor:</strong> {row['nome_inspetor']}<br>"

                                    f"<strong>Quantidade de Reprovações:</strong> {row['quantidade']}"

                                    f"</div>", unsafe_allow_html=True)

                # Segunda metade das perguntas reprovadas na segunda coluna

                with col2:

                    for index, row in tabela_perguntas.iloc[metade:].iterrows():
                        cor_inspetor = cores_inspetores[row['nome_inspetor']]  # Cor específica para o inspetor

                        st.markdown(f'<div class="card" style="background-color: {cor_inspetor};">'

                                    f"<strong>Equipe🛻 {row['num_operacional']}</strong><br>"

                                    f"<strong>Pergunta:</strong> {row['pergunta']}<br>"

                                    f"<strong>Inspetor:</strong> {row['nome_inspetor']}<br>"

                                    f"<strong>Quantidade de Reprovações:</strong> {row['quantidade']}"

                                    f"</div>", unsafe_allow_html=True)

#------------------------------------------------------------------------------------------------------------------------------------------
            # Grafico de Integrantes Por  Equipes -----------------------------------------------------------------

            if grafico_selecionado == "Dashboard":
                    st.title("Dashboard Inspeções Dinâmicas")

            elif grafico_selecionado == "Integrantes Equipes":
                st.title("Integrantes das Equipes")

                # Contar as blitz realizadas por equipe (turnos distintos)
                quantidade_blitz = (
                    df_filtrado.groupby('num_operacional')['idtb_turnos']
                    .nunique()  # Contando os turnos distintos (blitz realizadas)
                    .reset_index()
                    .rename(columns={'idtb_turnos': 'Quantidade_Blitz'})
                )

                # Agrupar por equipe para obter os integrantes e última data de inspeção
                tabela_inspecionadas = (
                    df_filtrado.groupby('num_operacional')
                    .agg(
                        Pessoas=('nome', lambda x: ', '.join(x.unique())),
                        Ultima_Inspecao=('data_blitz', 'max')
                    )
                    .reset_index()
                    .rename(columns={'num_operacional': 'Equipe'})
                )

                # Contar as blitz realizadas por equipe (turnos distintos)
                quantidade_blitz = (
                    df_filtrado.groupby('num_operacional')['idtb_turnos']
                    .nunique()  # Contando os turnos distintos (blitz realizadas)
                    .reset_index()
                    .rename(columns={'idtb_turnos': 'Quantidade_Blitz'})
                )

                # 1. Agrupar a quantidade de inspeções por equipe (usando idtb_turnos)
                blitz_por_equipe = df_filtrado.groupby("num_operacional").agg(
                    quantidade_inspecao=('idtb_turnos', 'nunique')).reset_index()

                # 2. Agrupar os nomes das pessoas por equipe
                tabela_inspecionadas = (
                    df_filtrado.groupby('num_operacional')
                    .agg(
                        Pessoas=('nome', lambda x: ', '.join(x.unique())),
                        Ultima_Inspecao=('data_blitz', 'max')
                    )
                    .reset_index()
                )

                # 3. Fazer o merge entre a tabela das inspeções e a tabela das pessoas
                tabela_inspecionadas = pd.merge(tabela_inspecionadas, blitz_por_equipe, on='num_operacional',
                                                how='left')

                # 4. Definir a quantidade máxima de inspeções para normalizar as cores
                max_inspecao = tabela_inspecionadas['quantidade_inspecao'].max()

                # 5. Função para determinar a cor da bolinha
                def get_circle_color(inspecao_count, max_count):
                    # Normaliza a quantidade de inspeções
                    normalized_value = inspecao_count / max_count if max_count > 0 else 0
                    # A cor varia de vermelho (menor inspeção) a verde (maior inspeção)
                    red = int((1 - normalized_value) * 255)  # Quanto maior a inspeção, menor o valor de vermelho
                    green = int(normalized_value * 255)  # Quanto maior a inspeção, maior o valor de verde
                    return f'rgb({red}, {green}, 0)'

                # 6. Dividir as equipes para exibir em duas colunas lado a lado
                col1, col2 = st.columns(2)  # Criando 2 colunas para exibir os cartões lado a lado

                # Dividir as equipes pela metade para cada coluna
                metade = len(tabela_inspecionadas) // 2

                # Estilo para o fundo dos cartões
                estilo_bilhetes = """
                    <style>
                    .card {
                        background-color: #F4E1D2;  /* Cor de fundo tipo bilhete */
                        padding: 20px;
                        margin-bottom: 10px;
                        border-radius: 10px;
                        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                        position: relative;  /* Para colocar a bolinha no canto */
                    }
                    .circle {
                        width: 20px;
                        height: 20px;
                        border-radius: 50%;
                        position: absolute;
                        top: 10px;
                        right: 10px;
                        border: 2px solid white;
                    }
                    </style>
                    """
                st.markdown(estilo_bilhetes, unsafe_allow_html=True)



                # Coluna 1: Primeira metade das equipes
                with col1:

                    for index, row in tabela_inspecionadas.iloc[:metade].iterrows():
                        # Definir a cor da bolinha
                        circle_color = get_circle_color(row['quantidade_inspecao'], max_inspecao)

                        # Cartão de equipe
                        with st.container():
                            st.markdown(f'<div class="card">'
                                        f'<div class="circle" style="background-color:{circle_color};"></div>'
                                        f"<strong>Equipe🛻 {row['num_operacional']}</strong><br>"
                                        f"<strong>Pessoas:</strong> {row['Pessoas']}<br>"
                                        f"<strong>Quantidade de Inspeções:</strong> {row['quantidade_inspecao']}<br>"
                                        f"<strong>Última Inspeção:</strong> {row['Ultima_Inspecao'].strftime('%d/%m/%Y')}"
                                        f"</div>", unsafe_allow_html=True)
                            st.markdown("<hr>", unsafe_allow_html=True)  # Barra de separação visual (linha horizontal)

                # Coluna 2: Segunda metade das equipes
                with col2:

                    for index, row in tabela_inspecionadas.iloc[metade:].iterrows():
                        # Definir a cor da bolinha
                        circle_color = get_circle_color(row['quantidade_inspecao'], max_inspecao)

                        # Cartão de equipe
                        with st.container():
                            st.markdown(f'<div class="card">'
                                        f'<div class="circle" style="background-color:{circle_color};"></div>'
                                        f"<strong>Equipe🛻 {row['num_operacional']}</strong><br>"
                                        f"<strong>Pessoas:</strong> {row['Pessoas']}<br>"
                                        f"<strong>Quantidade de Inspeções:</strong> {row['quantidade_inspecao']}<br>"
                                        f"<strong>Última Inspeção:</strong> {row['Ultima_Inspecao'].strftime('%d/%m/%Y')}"
                                        f"</div>", unsafe_allow_html=True)
                            st.markdown("<hr>", unsafe_allow_html=True)  # Barra de separação visual (linha horizontal)




    except Error as e:
        st.error(f"Erro ao conectar ao MariaDB: {e}")
    finally:
        if connection.is_connected():
            cursor.close()
            connection.close()

connect_to_mariadb()
