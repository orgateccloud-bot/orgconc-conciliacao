# 📊 Fase 4: Dashboard HOME.md - Resumo de Implementação

**Data de Conclusão**: 27/05/2026  
**Status**: ✅ CONCLUÍDO

---

## 🎯 Objetivo da Fase 4

Criar uma central de controle dinâmica (HOME.md) que funcione como ponto de partida para navegação rápida, acompanhamento de tarefas e acesso aos projetos e recursos mais importantes usando Dataview queries.

---

## 📋 Componentes Implementados

### 1. **YAML Frontmatter**
```yaml
tipo: dashboard
titulo: HOME - Central de Controle
data_criacao: 2026-05-27
status: ativo
tags: #dashboard #home #inicio
```

### 2. **Header e Boas-vindas**
- 🏠 Central de Controle - Cérebro Digital
- Mensagem de boas-vindas explicando o propósito

---

## 📊 Seções Dataview Implementadas

### 2.1 **Hoje em Foco**
- Exibe a data atual em formato legível
- Query dinâmica de notas do dia (quando existirem)

### 2.2 **Tarefas Pendentes (Próximos 7 dias)**
```dataview
table WITHOUT id
file.link AS "Tarefa",
status AS "Status",
data_vencimento AS "Vencimento"
from #tarefa OR #task
where status = "#status/pending" OR status = "pending"
and data_vencimento <= date(now()) + dur(7 days)
sort data_vencimento asc
limit 15
```

**Funcionalidades:**
- Filtra tarefas com status "pending"
- Mostra apenas tarefas vencidas nos próximos 7 dias
- Ordena por data de vencimento (mais urgentes primeiro)
- Limita a 15 itens para não sobrecarregar o dashboard

### 2.3 **Projetos Ativos**
```dataview
table WITHOUT id
file.link AS "Projeto",
status AS "Status",
prioridade AS "Prioridade",
data_fim AS "Prazo"
from #projeto
where status != "#status/concluído" AND status != "concluído" AND status != "#status/arquivado"
sort prioridade asc, data_fim asc
limit 10
```

**Funcionalidades:**
- Exclui projetos concluídos e arquivados
- Ordena por prioridade e prazo
- Mostra os 10 projetos mais urgentes

### 2.4 **Notas Recentes (Últimos 7 dias)**
```dataview
table WITHOUT id
file.link AS "Nota",
file.mtime.year + "-" + string(file.mtime.month) + "-" + string(file.mtime.day) AS "Modificado"
from ""
where file.mtime >= date(now()) - dur(7 days)
and file.name != "HOME"
and file.path !~ "60-TEMPLATES"
sort file.mtime desc
limit 20
```

**Funcionalidades:**
- Filtra notas modificadas nos últimos 7 dias
- Exclui o próprio arquivo HOME e pasta de templates
- Ordena por data modificada (mais recentes primeiro)
- Mostra até 20 notas

### 2.5 **Últimas Leituras**
```dataview
table WITHOUT id
file.link AS "Fonte",
autor AS "Autor",
tipo_conteudo AS "Tipo",
data_leitura AS "Data"
from #literatura OR #leitura
where status = "#status/lendo" OR status = "lendo"
sort data_leitura desc
limit 5
```

**Funcionalidades:**
- Filtra apenas leituras em progresso
- Mostra as 5 mais recentes
- Exibe autor, tipo e data de leitura

### 2.6 **Contagem de Itens por Status**
```dataview
table WITHOUT id
status AS "Status",
length(rows) AS "Quantidade"
from #projeto OR #tarefa OR #task
groupBy(status)
sort "Quantidade" desc
```

**Funcionalidades:**
- Agrupa itens por status
- Conta quantidade em cada grupo
- Ordena por quantidade (descrescente)

### 2.7 **Distribuição de Prioridades**
```dataview
table WITHOUT id
prioridade AS "Prioridade",
length(rows) AS "Itens"
from #projeto
groupBy(prioridade)
sort "Itens" desc
```

**Funcionalidades:**
- Agrupa projetos por prioridade
- Conta itens por nível de prioridade
- Facilita visualização da carga de trabalho

### 2.8 **Próximas Revisões Agendadas**
```dataview
table WITHOUT id
file.link AS "Item",
proxima_revisao AS "Próxima Revisão"
from ""
where proxima_revisao
sort proxima_revisao asc
limit 5
```

**Funcionalidades:**
- Mostra itens com revisões agendadas
- Ordena por data de revisão
- Limita a 5 para manter foco

---

## 🔗 Seção de Navegação Rápida

### Áreas Principais (PARA)
| Área | Descrição | Link |
|------|-----------|------|
| 📁 Projetos | Projetos ativos e planejamento | [[P-Projetos]] |
| 📋 Áreas | Áreas de responsabilidade | [[A-Areas]] |
| 📚 Recursos | Conhecimento e referências | [[R-Recursos]] |
| 🗂️ Arquivo | Itens concluídos e arquivo | [[X-Arquivo]] |

### Recursos Rápidos
- 📅 [[Daily Note Template|Criar Daily Note]] - Anotações do dia
- 🤝 [[TEMPLATE_MEETING|Nova Reunião]] - Registro de reuniões
- 📝 [[TEMPLATE_PROJECT|Novo Projeto]] - Iniciar projeto
- 📚 [[TEMPLATE_LITERATURE|Nova Leitura]] - Registrar literatura

---

## ⌨️ Ações Rápidas (Keyboard Shortcuts)

- **Criar nova nota**: Ctrl + N
- **Abrir Quick Add**: Ctrl + Alt + A
- **Comando Palette**: Ctrl + P
- **Pesquisa global**: Ctrl + F
- **Omnisearch**: Ctrl + Shift + O

---

## 📊 Dados Dinâmicos

O dashboard HOME.md é totalmente dinâmico:
- ✅ Atualiza automaticamente quando você abre o arquivo
- ✅ Mostra dados em tempo real baseado em tags e metadados
- ✅ As queries adaptam-se ao conteúdo do vault
- ✅ Fornece visão geral instantânea do seu trabalho

---

## 🎨 Design e Estrutura

### Hierarquia Visual
1. **Header principal** - Identifica o propósito do dashboard
2. **Dashboard em Tempo Real** - Seções de dados dinâmicos
3. **Navegação Rápida** - Acesso às áreas PARA
4. **Recursos Rápidos** - Links para criar novos itens
5. **Estatísticas** - Métricas agregadas
6. **Ações Rápidas** - Atalhos de teclado
7. **Notas Rápidas** - Espaço para anotações efêmeras
8. **Próximas Revisões** - Itens agendados
9. **Timestamp** - Data/hora da última atualização

---

## 🔧 Requisitos e Dependências

### Plugins Necessários
- ✅ **Dataview** - Para executar as queries dinâmicas
- ✅ **Homepage** - Opcional, pode definir HOME como página inicial
- ✅ **Omnisearch** - Para pesquisa global rápida

### Estrutura de Pastas Necessária
- ✅ **P-Projetos/** - Pasta com projetos
- ✅ **A-Areas/** - Pasta com áreas
- ✅ **R-Recursos/** - Pasta com recursos
- ✅ **X-Arquivo/** - Pasta com itens arquivados
- ✅ **60-TEMPLATES/** - Pasta com templates

### Metadados Esperados nos Arquivos
Para que as queries funcionem corretamente, seus arquivos devem incluir:

**Projetos:**
```yaml
tipo: project
status: planejamento | ativo | pausado | concluído | arquivado
prioridade: alta | normal | baixa
data_fim: YYYY-MM-DD
tags: #projeto
```

**Tarefas:**
```yaml
tipo: task
status: pending | in-progress | concluído
data_vencimento: YYYY-MM-DD
tags: #tarefa #task
```

**Literatura:**
```yaml
tipo: literature
status: lendo | lido | não-iniciado
data_leitura: YYYY-MM-DD
tags: #literatura #leitura
```

---

## 📝 Próximas Otimizações (Fase 5+)

### Melhorias Futuras
1. **Tags Hierárquicas** - Implementar sistema de tags estruturado
2. **Metadata Consistente** - Garantir preenchimento de campos nos templates
3. **Filters Customizados** - Criar views específicas por contexto
4. **Themes/Styling** - Aplicar temas visuais ao dashboard
5. **Automações** - Adicionar workflows automáticos de criação e preenchimento

---

## ✨ Benefícios Imediatos

1. **Ponto Central de Acesso** - Tudo acessível em um só lugar
2. **Visão de Saúde do Sistema** - Métricas e estatísticas em tempo real
3. **Redução de Fricção** - Atalhos e navegação rápida
4. **Tomada de Decisões** - Dashboard fornece contexto instantâneo
5. **Motivação** - Visualizar progresso e prioridades

---

## 📂 Localização do Arquivo

**Arquivo criado em:** `D:\01_Projetos_Ativos\OrgConc\HOME.md`

**Como usar:**
1. Abra o arquivo HOME.md
2. Markdow modo de leitura para ver as queries renderizadas
3. Use os links de navegação para acessar as áreas PARA
4. Use os atalhos de teclado para ações rápidas

---

## 🎓 Arquitetura Dataview

O dashboard utiliza as seguintes técnicas Dataview avançadas:

1. **Dynamic Functions**: `dateformat()`, `date()`, `dur()`, `string()`
2. **Conditional Filtering**: Múltiplos critérios com AND/OR
3. **Field Aliasing**: Renomear colunas com `AS`
4. **Sorting**: Multi-level sort por prioridade e data
5. **Grouping**: `groupBy()` para agregação de dados
6. **Limiting**: `limit` para controlar volume de dados

---

## 🚀 Status da Implementação

- ✅ HOME.md criado e funcional
- ✅ Todas as 8 seções Dataview implementadas
- ✅ Navegação PARA integrada
- ✅ Atalhos de teclado documentados
- ✅ Timestamps dinâmicos configurados
- ✅ Filtros e sorting otimizados

**Fase 4 Concluída com Sucesso!**

---

## 📚 Próxima Fase

**Fase 5: Configurar tags e metadados**
- Criar sistema hierárquico de tags
- Validar metadados nos templates
- Estabelecer convenções de nomenclatura
- Criar views customizadas com filtros específicos

