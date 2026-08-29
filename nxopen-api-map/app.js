(function(){
  'use strict';
  var DATA = window.NXOPEN_DATA || [];
  var HAS_DATA = !!(DATA && DATA.length);

  // ============ 数据加载检查 ============
  // 若 data/nxopen_data.js 未加载（文件缺失/404），不再无限转圈，
  // 而是将 loading 遮罩转为明确的错误提示，并停止后续初始化。
  if(!HAS_DATA){
    var loadingEl = document.getElementById('loading');
    if(loadingEl){
      loadingEl.innerHTML =
        '<div style="text-align:left;max-width:420px;line-height:1.7">' +
          '<div style="font-size:14px;font-weight:600;color:#f85149;margin-bottom:8px">⚠️ 数据文件未加载</div>' +
          '<div style="font-size:12px;color:#8b949e">未找到 <code style="color:#58a6ff">data/nxopen_data.js</code>。' +
          '本地打开请确认该文件存在于 <code>data/</code> 目录；' +
          '若部署到 GitHub Pages，请确认仓库中已提交该文件（本项目 .gitignore 不忽略它，需正常 git add）。</div>' +
        '</div>';
      loadingEl.style.display = 'flex';
    }
    return;
  }

  // ============ Stats ============
  var totalMods=0, totalCls=0, totalMethods=0, totalProps=0;
  DATA.forEach(function(d){
    totalMods += d.mods.length;
    d.mods.forEach(function(m){
      totalCls += m.c.length;
      m.c.forEach(function(c){
        (c[2]||[]).forEach(function(meth){
          if(meth.pr === 1) totalProps++;
          else totalMethods++;
        });
      });
    });
  });
  document.getElementById('stats').innerHTML =
    '<span>功能域 <b>' + DATA.length + '</b></span>' +
    '<span>模块 <b>' + totalMods + '</b></span>' +
    '<span>类 <b>' + totalCls.toLocaleString() + '</b></span>' +
    '<span>方法 <b>' + totalMethods.toLocaleString() + '</b></span>' +
    '<span>属性 <b>' + totalProps.toLocaleString() + '</b></span>';

  // ============ Color palette ============
  var colors = ['#58a6ff','#f0883e','#3fb950','#bc8cff','#f778ba','#ffa657','#79c0ff','#56d4dd','#ff7b72','#d2a8ff','#a5d6ff','#7ee787'];
  var domainColors = {};
  DATA.forEach(function(d,i){ domainColors[d.n] = colors[i % colors.length]; });

  // ============ Build tree data ============
  function buildTree(){
    var root = {name:'NXOpen', type:'root', children:[]};
    DATA.forEach(function(d){
      var dNode = {name:d.n, type:'domain', color:domainColors[d.n], cc:d.cc, mc:d.mc, _collapsed:true, children:[]};
      d.mods.forEach(function(m){
        dNode.children.push({name:m.n, type:'module', color:domainColors[d.n], desc:m.d, cls:m.c, _collapsed:true});
      });
      root.children.push(dNode);
    });
    return root;
  }

  var treeRoot = buildTree();
  var svgEl = d3.select('#mindmap-svg');
  var svgNode = document.getElementById('mindmap-svg');

  var g = svgEl.append('g').attr('transform','translate(60,40)');
  var gLink = g.append('g').attr('class','links');
  var gNode = g.append('g').attr('class','nodes');

  var zoom = d3.zoom().scaleExtent([0.3,3]).on('zoom', function(e){
    g.attr('transform', e.transform);
    document.getElementById('zoom-info').textContent = Math.round(e.transform.k*100) + '%';
  });
  svgEl.call(zoom);
  svgEl.on('dblclick.zoom', null);

  var tree = d3.tree().nodeSize([36, 200]);
  treeRoot.children[0]._collapsed = true;  // all collapsed by default

  function getVisible(node){
    if(node._collapsed) return null;
    return node.children || null;
  }

  function update(source){
    var root = d3.hierarchy(treeRoot, function(d){ return getVisible(d); });
    tree(root);
    var nodes = root.descendants();
    var links = root.links();

    gLink.selectAll('path').data(links).join('path')
      .attr('class','link')
      .attr('d', d3.linkHorizontal().x(function(d){return d.y;}).y(function(d){return d.x;}));

    var nodeSel = gNode.selectAll('g.node').data(nodes, function(d){ return d.data.name + (d.depth||0); });
    var nodeEnter = nodeSel.enter().append('g')
      .attr('class', function(d){ return 'node ' + d.data.type; })
      .attr('transform', function(d){ return 'translate(' + d.y + ',' + d.x + ')'; })
      .on('click', function(e,d){ nodeClick(e,d); });

    nodeEnter.append('circle')
      .attr('r', function(d){ return d.data.type==='root' ? 6 : d.data.type==='domain' ? 5 : 3.5; })
      .attr('fill', function(d){ return d.data.type==='root' ? '#58a6ff' : d.data.color || '#58a6ff'; })
      .attr('stroke','#0d1117')
      .attr('stroke-width',2);

    nodeEnter.append('text')
      .attr('class','collapse-icon')
      .attr('text-anchor','middle')
      .attr('y', 3)
      .attr('font-size','9px')
      .attr('fill','#0d1117')
      .attr('font-weight','bold')
      .text(function(d){ return (d.data._collapsed && d.data.children) ? '+' : ''; });

    nodeEnter.append('text')
      .attr('x', function(d){ return d.data.type==='root' ? -12 : 10; })
      .attr('dy', function(d){ return d.data.type==='root' ? '-0.4em' : '0.32em'; })
      .attr('text-anchor', function(d){ return d.data.type==='root' ? 'end' : 'start'; })
      .text(function(d){ return d.data.name; });

    nodeSel.merge(nodeEnter)
      .attr('transform', function(d){ return 'translate(' + d.y + ',' + d.x + ')'; });

    nodeSel.merge(nodeEnter).select('circle')
      .attr('r', function(d){ return d.data.type==='root' ? 6 : d.data.type==='domain' ? 5 : 3.5; })
      .attr('fill', function(d){
        if(d.data.type==='root') return '#58a6ff';
        return d.data._collapsed ? (d.data.color||'#58a6ff') : '#0d1117';
      })
      .attr('stroke', function(d){ return d.data.color || '#58a6ff'; })
      .attr('stroke-width', 2);

    nodeSel.merge(nodeEnter).select('.collapse-icon')
      .text(function(d){ return (d.data._collapsed && d.data.children) ? '+' : ''; });

    nodeSel.exit().remove();
    document.getElementById('loading').style.display = 'none';
    setTimeout(fitScreen, 100);
  }

  function fitScreen(){
    var bounds = gNode.node().getBBox();
    var fullWidth = svgNode.clientWidth;
    var fullHeight = svgNode.clientHeight;
    if(bounds.width===0 || bounds.height===0) return;
    var midW = fullWidth/2;
    var midH = fullHeight/2;
    var scale = Math.min(0.9, fullWidth/(bounds.width+120), fullHeight/(bounds.height+60));
    scale = Math.max(0.5, scale);  // don't zoom out too far
    var tx = midW - (bounds.x + bounds.width/2)*scale;
    var ty = midH - (bounds.y + bounds.height/2)*scale;
    svgEl.transition().duration(500).call(zoom.transform, d3.zoomIdentity.translate(tx,ty).scale(scale));
  }

  function nodeClick(event, d){
    event.stopPropagation();
    var nodeData = d.data;
    if(nodeData.type==='root') return;
    if(nodeData.type==='domain'){
      nodeData._collapsed = !nodeData._collapsed;
      update(d);
    } else if(nodeData.type==='module'){
      showModuleDetail(nodeData);
      if(nodeData.children){
        nodeData._collapsed = !nodeData._collapsed;
        update(d);
      }
    }
  }

  document.getElementById('btn-fit').addEventListener('click', fitScreen);
  document.getElementById('btn-collapse').addEventListener('click', function(){
    var btn = document.getElementById('btn-collapse');
    if(btn.textContent === '全部折叠'){
      // Collapse all domains → only show domain circles
      treeRoot.children.forEach(function(d){ d._collapsed = true; });
      btn.textContent = '全部展开';
    } else {
      // Expand all domains, collapse all modules → show domain → module
      treeRoot.children.forEach(function(d){
        d._collapsed = false;
        if(d.children) d.children.forEach(function(m){ m._collapsed = true; });
      });
      btn.textContent = '全部折叠';
    }
    update(treeRoot);
  });

  // ============ Detail Panel ============
  var detailPanel = document.getElementById('detail-panel');
  var breadcrumb = [];
  var panelSearch = {q: '', filter: {cls: true, method: true, prop: true}};
  var panelCtx = null;
  var panelSearchTimer = null;

  function renderPanelSearch(clsCount, methodCount, propCount){
    var html = '<div class="panel-search-box">';
    html += '<div class="ps-input-wrap">';
    html += '<input type="text" class="ps-input" id="ps-input" placeholder="在当前面板搜索..." value="' + escapeAttr(panelSearch.q) + '">';
    html += '<span class="ps-clear" id="ps-clear"' + (panelSearch.q ? '' : ' style="display:none"') + '>✕</span>';
    html += '</div>';
    html += '<div class="ps-tabs">';
    if(clsCount > 0) html += '<span class="ps-tab' + (panelSearch.filter.cls ? ' active' : '') + '" data-psf="cls">类</span>';
    if(methodCount > 0) html += '<span class="ps-tab' + (panelSearch.filter.method ? ' active' : '') + '" data-psf="method">方法</span>';
    if(propCount > 0) html += '<span class="ps-tab' + (panelSearch.filter.prop ? ' active' : '') + '" data-psf="prop">属性</span>';
    html += '</div>';
    html += '</div>';
    return html;
  }

  function applyPanelSearch(){
    if(!panelCtx) return;
    var contentEl = document.getElementById('panel-content');
    if(!contentEl) return;
    contentEl.innerHTML = panelCtx.type === 'module' ? renderModuleContent() : renderClassContent();
    var clearBtn = document.getElementById('ps-clear');
    if(clearBtn) clearBtn.style.display = panelSearch.q ? '' : 'none';
  }

  function panelMatch(name, q){
    if(!q) return true;
    return name.toLowerCase().indexOf(q) >= 0;
  }

  function renderBreadcrumb(){
    if(breadcrumb.length===0) return '';
    var html = '';
    breadcrumb.forEach(function(b,i){
      if(i>0) html += '<span class="bc-sep">/</span>';
      var isLast = i===breadcrumb.length-1;
      html += '<span class="bc-item ' + (isLast?'bc-current':'') + '" data-idx="' + i + '">' + escapeHtml(b.label) + '</span>';
    });
    return '<div class="breadcrumb">' + html + '</div>';
  }

  detailPanel.addEventListener('click', function(e){
    var bcItem = e.target.closest('.bc-item');
    if(bcItem){
      var idx = parseInt(bcItem.dataset.idx);
      breadcrumb = breadcrumb.slice(0, idx+1);
      var item = breadcrumb[idx];
      if(item.action) item.action();
      return;
    }
    // Module filter tab toggle (now uses panelSearch.filter)
    var ftab = e.target.closest('.mod-tab');
    if(ftab){
      e.stopPropagation();
      var key = ftab.dataset.ftab;
      panelSearch.filter[key] = !panelSearch.filter[key];
      ftab.classList.toggle('active', panelSearch.filter[key]);
      applyPanelSearch();
      return;
    }
    // Panel search filter tab toggle
    var psTab = e.target.closest('.ps-tab');
    if(psTab){
      e.stopPropagation();
      var psfKey = psTab.dataset.psf;
      panelSearch.filter[psfKey] = !panelSearch.filter[psfKey];
      psTab.classList.toggle('active', panelSearch.filter[psfKey]);
      applyPanelSearch();
      return;
    }
    // Panel search clear
    if(e.target.id === 'ps-clear' || e.target.closest('#ps-clear')){
      e.stopPropagation();
      panelSearch.q = '';
      var psInput = document.getElementById('ps-input');
      if(psInput) psInput.value = '';
      applyPanelSearch();
      if(psInput) psInput.focus();
      return;
    }
    // Module-level method item click
    var modMethod = e.target.closest('.mod-method-item');
    if(modMethod){
      var mm = modMethod.dataset.mod;
      var mc2 = modMethod.dataset.cls;
      var mname = modMethod.dataset.method;
      var domain = findDomain(mm);
      if(domain){
        var mod = domain.mods.find(function(m){ return m.n === mm; });
        if(mod){
          var cls = mod.c.find(function(c){ return c[0] === mc2; });
          if(cls) showClassDetail(mod, cls);
          if(mname){
            setTimeout(function(){
              var items = detailPanel.querySelectorAll('.method-item');
              for(var j=0; j<items.length; j++){
                var nameEl = items[j].querySelector('.mi-name');
                if(nameEl && nameEl.textContent.indexOf(mname) === 0){
                  items[j].style.border = '2px solid #58a6ff';
                  items[j].scrollIntoView({behavior:'smooth', block:'center'});
                  break;
                }
              }
            }, 100);
          }
        }
      }
      return;
    }
    var card = e.target.closest('.class-card');
    if(card){
      var modName = card.dataset.mod;
      var clsName = card.dataset.cls;
      var domain = findDomain(modName);
      if(domain){
        var mod = domain.mods.find(function(m){ return m.n === modName; });
        if(mod){
          var cls = mod.c.find(function(c){ return c[0] === clsName; });
          if(cls) showClassDetail(mod, cls);
        }
      }
    }
    // Nested class card click
    var subCard = e.target.closest('.cd-sub-card');
    if(subCard){
      var modName2 = subCard.dataset.mod;
      var clsName2 = subCard.dataset.cls;
      var domain2 = findDomain(modName2);
      if(domain2){
        var mod2 = domain2.mods.find(function(m){ return m.n === modName2; });
        if(mod2){
          var cls2 = mod2.c.find(function(c){ return c[0] === clsName2; });
          if(cls2) showClassDetail(mod2, cls2);
        }
      }
    }
    // Inheritance card click (parent/child classes)
    var inhCard = e.target.closest('.cd-inherit-card.clickable');
    if(inhCard){
      var modName3 = inhCard.dataset.mod;
      var clsName3 = inhCard.dataset.cls;
      var domain3 = findDomain(modName3);
      if(domain3){
        var mod3 = domain3.mods.find(function(m){ return m.n === modName3; });
        if(mod3){
          var cls3 = mod3.c.find(function(c){ return c[0] === clsName3; });
          if(cls3) showClassDetail(mod3, cls3);
        }
      }
    }
    // Type link click (parameter/return type jumping to class)
    var typeLink = e.target.closest('.type-link');
    if(typeLink){
      var tlMod = typeLink.dataset.mod;
      var tlCls = typeLink.dataset.cls;
      var tlDomain = findDomain(tlMod);
      if(tlDomain){
        var tlModNode = tlDomain.mods.find(function(m){ return m.n === tlMod; });
        if(tlModNode){
          var tlClsNode = tlModNode.c.find(function(c){ return c[0] === tlCls; });
          if(tlClsNode) showClassDetail(tlModNode, tlClsNode);
        }
      }
    }
  });
  // Panel search input handler (debounced)
  detailPanel.addEventListener('input', function(e){
    if(e.target.id === 'ps-input'){
      if(panelSearchTimer) clearTimeout(panelSearchTimer);
      panelSearchTimer = setTimeout(function(){
        panelSearch.q = e.target.value;
        applyPanelSearch();
      }, 200);
    }
  });
  // Panel search Enter key
  detailPanel.addEventListener('keydown', function(e){
    if(e.target.id === 'ps-input' && e.key === 'Enter'){
      e.preventDefault();
      panelSearch.q = e.target.value;
      applyPanelSearch();
    }
  });

  function showModuleDetail(modNode){
    var modName = modNode.n || modNode.name || '';
    breadcrumb = [{label: modName, action: function(){ showModuleDetail(modNode); }}];
    var clsList = modNode.cls || modNode.c || [];
    // Count methods and properties separately
    var methodCount = 0, propCount = 0;
    clsList.forEach(function(c){
      (c[2]||[]).forEach(function(m){
        if(m.pr === 1) propCount++; else methodCount++;
      });
    });
    // Reset panel search on view change
    panelSearch.q = '';
    panelSearch.filter = {cls: true, method: true, prop: true};
    panelCtx = {type:'module', modNode: modNode, clsList: clsList, methodCount: methodCount, propCount: propCount};
    var html = renderBreadcrumb();
    html += '<div class="module-detail"><div class="mod-header">';
    html += '<h2>' + escapeHtml(modName) + '</h2>';
    if(modNode.desc) html += '<div class="mod-desc">' + escapeHtml(cleanText(modNode.desc)) + '</div>';
    if(modNode.d && !modNode.desc) html += '<div class="mod-desc">' + escapeHtml(cleanText(modNode.d)) + '</div>';
    // Toggle tabs — three independent toggles, hide when count is 0
    html += '<div class="mod-stats">';
    if(clsList.length > 0) html += '<span class="mod-tab' + (panelSearch.filter.cls ? ' active' : '') + '" data-ftab="cls">类' + clsList.length + '</span>';
    if(methodCount > 0) html += '<span class="mod-tab' + (panelSearch.filter.method ? ' active' : '') + '" data-ftab="method">方法 ' + methodCount + '</span>';
    if(propCount > 0) html += '<span class="mod-tab' + (panelSearch.filter.prop ? ' active' : '') + '" data-ftab="prop">属性' + propCount + '</span>';
    html += '</div>';
    // Panel search box (with class tab — aligned with method/prop tabs)
    html += renderPanelSearch(clsList.length, methodCount, propCount);
    html += '</div>';
    // Content area (re-rendered on search/filter change)
    html += '<div id="panel-content">';
    html += renderModuleContent();
    html += '</div>';
    html += '</div>';
    detailPanel.innerHTML = html;
    detailPanel.scrollTop = 0;
  }

  function renderModuleContent(){
    if(!panelCtx || panelCtx.type !== 'module') return '';
    var modNode = panelCtx.modNode;
    var clsList = panelCtx.clsList;
    var modName = modNode.n || modNode.name || '';
    var methodCount = panelCtx.methodCount, propCount = panelCtx.propCount;
    var q = panelSearch.q.trim().toLowerCase();
    var html = '';
    var anyActive = panelSearch.filter.cls || (methodCount > 0 && panelSearch.filter.method) || (propCount > 0 && panelSearch.filter.prop);
    if(!anyActive){
      html += '<div class="empty-state">请至少选择一个标签</div>';
      return html;
    }
    // Class list
    if(panelSearch.filter.cls){
      var matchingCls = clsList;
      if(q){
        matchingCls = clsList.filter(function(c){
          var sn = c[0].split('.').pop().toLowerCase();
          return sn.indexOf(q) >= 0 || c[0].toLowerCase().indexOf(q) >= 0;
        });
      }
      var clsLabel = q ? '类列表 (' + matchingCls.length + '/' + clsList.length + ')' : '类列表 (' + clsList.length + ')';
      html += '<div class="cd-sub-title" style="color:#58a6ff;border-left-color:#58a6ff;margin-bottom:10px">📦 ' + clsLabel + '</div>';
      if(matchingCls.length === 0){
        html += '<div class="empty-state">无匹配类</div>';
      } else {
        html += '<div class="class-list">';
        var clsShown = 0;
        var clsMax = 500;
        matchingCls.forEach(function(cls){
          if(clsShown >= clsMax) return;
          var mc = (cls[2]||[]).length;
          var subCount = (cls[3]||[]).length;
          var displayNum = subCount > 0 ? subCount : mc;
          var shortName = cls[0].split('.').pop();
          html += '<div class="class-card" data-mod="' + escapeAttr(modName) + '" data-cls="' + escapeAttr(cls[0]) + '" title="' + escapeAttr(cls[0]) + '">';
          html += '<div class="cc-name">' + escapeHtml(shortName) + ' <span class="cc-method-count">' + displayNum + '</span></div>';
          if(cls[1]) html += '<div class="cc-doc">' + escapeHtml(cleanText(cls[1])) + '</div>';
          else html += '<div class="cc-doc" style="color:#484f58">(无描述)</div>';
          html += '</div>';
          clsShown++;
        });
        if(matchingCls.length > clsMax){
          html += '<div class="mod-method-more">仅显示前 ' + clsMax + ' 个，共 ' + matchingCls.length + ' 个</div>';
        }
        html += '</div>';
      }
    }
    // Method / property list
    if(panelSearch.filter.method || panelSearch.filter.prop){
      var allItems = [];
      clsList.forEach(function(cls){
        var clsShort = cls[0].split('.').pop();
        (cls[2]||[]).forEach(function(m){
          if(!m.n) return;
          var isProp = m.pr === 1;
          if(isProp && !panelSearch.filter.prop) return;
          if(!isProp && !panelSearch.filter.method) return;
          if(q && m.n.toLowerCase().indexOf(q) < 0) return;
          allItems.push({m:m, cls:cls[0], clsShort:clsShort, isProp:isProp});
        });
      });
      var maxShow = q ? 500 : 300;
      html += '<div class="mod-method-section">';
      if(!panelSearch.filter.cls || q){
        var label = '';
        if(panelSearch.filter.method && panelSearch.filter.prop) label = '方法与属性';
        else if(panelSearch.filter.method) label = '方法';
        else label = '属性';
        var countLabel = q ? (allItems.length + ' 匹配') : (allItems.length + '');
        html += '<div class="cd-sub-title" style="color:#8b949e;border-left-color:#8b949e;margin-bottom:10px">📋 ' + label + ' (' + countLabel + ')</div>';
      }
      if(allItems.length === 0){
        html += '<div class="empty-state">无匹配方法或属性</div>';
      } else {
        var shown = 0;
        allItems.forEach(function(item){
          if(shown >= maxShow) return;
          var m = item.m, isProp = item.isProp, clsShort = item.clsShort;
          var tag = isProp ? '<span class="mi-tag prop">属性</span>' : '<span class="mi-tag method">方法</span>';
          html += '<div class="mod-method-item" data-mod="' + escapeAttr(modName) + '" data-cls="' + escapeAttr(item.cls) + '" data-method="' + escapeAttr(m.n) + '">';
          html += '<div class="mod-mi-header">' + tag;
          html += '<span class="mod-mi-name">' + escapeHtml(m.n) + (isProp ? '' : '()') + '</span>';
          html += '<span class="mod-mi-cls">' + escapeHtml(clsShort) + '</span>';
          html += '</div>';
          if(m.d) html += '<div class="mod-mi-desc">' + escapeHtml(cleanText(m.d).substring(0, 120)) + '</div>';
          html += '</div>';
          shown++;
        });
        if(allItems.length > maxShow){
          html += '<div class="mod-method-more">仅显示前 ' + maxShow + ' 个，共 ' + allItems.length + ' 个</div>';
        }
      }
      html += '</div>';
    }
    return html;
  }

  function showClassDetail(modNode, cls){
    var className = cls[0];
    var shortName = className.split('.').pop();
    var classDoc = cleanText(cls[1] || '');
    var methods = cls[2] || [];
    var subClasses = cls[3] || [];  // nested classes: [[shortName, fullName, methodCount], ...]
    var modName = modNode.n || modNode.name || '';
    // Detect if this is a nested class (has an outer/parent class in the same module)
    var outerFull = className.lastIndexOf('.') >= 0 ? className.substring(0, className.lastIndexOf('.')) : '';
    var outerCls = null;
    if(outerFull && outerFull !== modName){
      var clsList = modNode.cls || modNode.c || [];
      outerCls = clsList.find(function(c){ return c[0] === outerFull; });
    }
    breadcrumb = [
      {label: modName, action: function(){ showModuleDetail(modNode); }},
      {label: shortName, action: function(){ showClassDetail(modNode, cls); }}
    ];
    var html = renderBreadcrumb();
    html += '<div class="class-detail"><div class="cd-header">';
    html += '<h3>' + escapeHtml(shortName) + '</h3>';
    if(className !== shortName) html += '<div class="cd-fullname">' + escapeHtml(className) + '</div>';
    if(classDoc) html += '<div class="cd-doc">' + escapeHtml(classDoc) + '</div>';
    var methodNum = 0, propNum = 0;
    methods.forEach(function(m){ if(m.pr === 1) propNum++; else methodNum++; });
    var parents = (cls.length > 4 && cls[4]) ? cls[4] : [];
    var children = (cls.length > 5 && cls[5]) ? cls[5] : [];
    var statsHtml = '';
    if(methodNum > 0) statsHtml += '<span class="stat-method">方法 ' + methodNum + '</span>';
    if(propNum > 0) statsHtml += '<span class="stat-prop">属性 ' + propNum + '</span>';
    if(subClasses.length > 0) statsHtml += '<span class="stat-nested">嵌套类 ' + subClasses.length + '</span>';
    if(parents.length > 0) statsHtml += '<span class="stat-parent">父类 ' + parents.length + '</span>';
    if(children.length > 0) statsHtml += '<span class="stat-child">子类 ' + children.length + '</span>';
    if(outerCls) statsHtml += '<span class="stat-outer">外层类 1</span>';
    if(statsHtml) html += '<div class="mod-stats" style="margin-top:8px">' + statsHtml + '</div>';
    html += '</div>';
    // Panel search box (with class tab for nested classes)
    if(subClasses.length > 0 || methods.length > 0){
      html += renderPanelSearch(subClasses.length, methodNum, propNum);
    }
    // Outer class section (for nested classes)
    if(outerCls){
      var outerShort = outerFull.split('.').pop();
      html += '<div class="cd-inherit-section">';
      html += '<div class="cd-inherit-title outer">↰ 外层类</div>';
      html += '<div class="cd-inherit-list">';
      html += '<div class="cd-inherit-card clickable outer" data-mod="' + escapeAttr(modName) + '" data-cls="' + escapeAttr(outerFull) + '">';
      html += '<span class="cd-inherit-name">' + escapeHtml(outerShort) + '</span>';
      html += '</div></div></div>';
    }

    // Parent classes section
    if(parents.length > 0){
      html += '<div class="cd-inherit-section">';
      html += '<div class="cd-inherit-title parent">⬆ 父类 (' + parents.length + ')</div>';
      html += '<div class="cd-inherit-list">';
      parents.forEach(function(p){
        var pDisplay = p[0], pMod = p[1], pFull = p[2];
        if(pMod && pFull){
          html += '<div class="cd-inherit-card clickable parent" data-mod="' + escapeAttr(pMod) + '" data-cls="' + escapeAttr(pFull) + '">';
          html += '<span class="cd-inherit-name">' + escapeHtml(pDisplay) + '</span>';
          if(pMod !== pDisplay) html += '<span class="cd-inherit-path">' + escapeHtml(pMod) + '</span>';
          html += '</div>';
        } else {
          html += '<div class="cd-inherit-card external"><span class="cd-inherit-name">' + escapeHtml(pDisplay) + '</span><span class="cd-inherit-badge">外部</span></div>';
        }
      });
      html += '</div></div>';
    }

    // Child classes (subclasses) section
    if(children.length > 0){
      html += '<div class="cd-inherit-section">';
      html += '<div class="cd-inherit-title child">⬇ 子类 (' + children.length + ')</div>';
      html += '<div class="cd-inherit-list">';
      var maxChl = 300;
      var shownChl = 0;
      children.forEach(function(ch){
        if(shownChl >= maxChl) return;
        html += '<div class="cd-inherit-card clickable child" data-mod="' + escapeAttr(ch[1]) + '" data-cls="' + escapeAttr(ch[2]) + '">';
        html += '<span class="cd-inherit-name">' + escapeHtml(ch[0]) + '</span>';
        if(ch[1] !== ch[0]) html += '<span class="cd-inherit-path">' + escapeHtml(ch[1]) + '</span>';
        html += '</div>';
        shownChl++;
      });
      if(children.length > maxChl){
        html += '<div class="mod-method-more">仅显示前 ' + maxChl + ' 个，共 ' + children.length + ' 个子类</div>';
      }
      html += '</div></div>';
    }
    // Panel content (re-rendered on search/filter change)
    panelCtx = {type:'class', modNode: modNode, cls: cls, methods: methods, subClasses: subClasses, modName: modName};
    panelSearch.q = '';
    panelSearch.filter = {cls: true, method: true, prop: true};
    html += '<div id="panel-content">';
    html += renderClassContent();
    html += '</div>';
    html += '</div>';
    detailPanel.innerHTML = html;
    detailPanel.scrollTop = 0;
  }

  function renderClassContent(){
    if(!panelCtx || panelCtx.type !== 'class') return '';
    var modNode = panelCtx.modNode;
    var cls = panelCtx.cls;
    var methods = panelCtx.methods;
    var subClasses = panelCtx.subClasses;
    var modName = panelCtx.modName;
    var q = panelSearch.q.trim().toLowerCase();
    var html = '';
    // Nested classes section (filtered by 类 tab + search)
    if(subClasses.length > 0 && panelSearch.filter.cls){
      var matchingSub = subClasses;
      if(q){
        matchingSub = subClasses.filter(function(sc){
          return sc[0].toLowerCase().indexOf(q) >= 0 || (sc[1]||'').toLowerCase().indexOf(q) >= 0;
        });
      }
      var subLabel = q ? '嵌套类 (' + matchingSub.length + '/' + subClasses.length + ')' : '嵌套类 (' + subClasses.length + ')';
      html += '<div class="cd-sub-section">';
      html += '<div class="cd-sub-title">⚙ ' + subLabel + '</div>';
      if(matchingSub.length === 0){
        html += '<div class="empty-state">无匹配嵌套类</div>';
      } else {
        html += '<div class="cd-sub-list">';
        var maxSub = 300;
        var shownSub = 0;
        matchingSub.forEach(function(sc){
          if(shownSub >= maxSub) return;
          html += '<div class="cd-sub-card" data-mod="' + escapeAttr(modName) + '" data-cls="' + escapeAttr(sc[1]) + '">';
          html += '<span class="cd-sub-name">' + escapeHtml(sc[0]) + '</span>';
          if(sc[2] > 0) html += '<span class="cd-sub-count">' + sc[2] + '</span>';
          html += '</div>';
          shownSub++;
        });
        if(matchingSub.length > maxSub){
          html += '<div class="mod-method-more">仅显示前 ' + maxSub + ' 个，共 ' + matchingSub.length + ' 个</div>';
        }
        html += '</div>';
      }
      html += '</div>';
    }
    // Method/property list (filtered by 方法/属性 tab + search)
    var hasMethodTab = panelSearch.filter.method || panelSearch.filter.prop;
    if(hasMethodTab && methods.length > 0){
      var matchingMethods = methods.filter(function(m){
        if(!m.n) return false;
        var isProp = m.pr === 1;
        if(isProp && !panelSearch.filter.prop) return false;
        if(!isProp && !panelSearch.filter.method) return false;
        if(q && m.n.toLowerCase().indexOf(q) < 0) return false;
        return true;
      });
      // Title
      var methodNum2 = 0, propNum2 = 0;
      methods.forEach(function(m){ if(m.n){ if(m.pr === 1) propNum2++; else methodNum2++; } });
      var titleParts = [];
      if(panelSearch.filter.method && methodNum2 > 0) titleParts.push('方法 ' + methodNum2);
      if(panelSearch.filter.prop && propNum2 > 0) titleParts.push('属性 ' + propNum2);
      if(q) titleParts = ['匹配 ' + matchingMethods.length + '/' + (methodNum2 + propNum2)];
      if(titleParts.length > 0){
        html += '<div class="cd-sub-title" style="color:#8b949e;border-left-color:#8b949e;margin-bottom:12px">📋 ' + titleParts.join(' · ') + '</div>';
      }
      html += '<div class="method-list">';
      if(matchingMethods.length === 0){
        html += '<div class="empty-state">无匹配方法或属性</div>';
      } else {
        matchingMethods.forEach(function(m){
          html += renderMethodCard(m);
        });
      }
      html += '</div>';
    }
    if(methods.length === 0 && subClasses.length === 0){
      html += '<div class="empty-state">该类没有公开方法或属性</div>';
    }
    return html;
  }

  // ============ Render method card (FULL details) ============
  function renderMethodCard(m){
    var isProp = m.pr === 1;
    var html = '<div class="method-item' + (isProp ? ' method-prop' : '') + '">';

    // Header: tag + name
    var tag = isProp ? '<span class="mi-tag prop">属性</span>' : '<span class="mi-tag method">方法</span>';
    html += '<div class="mi-header">' + tag;
    html += '<span class="mi-name">' + escapeHtml(m.n) + (isProp ? '' : '()') + '</span>';
    html += '</div>';

    // Signature
    if(m.s){
      html += '<div class="mi-sig"><span class="mi-sig-label">签名</span> <code>' + escapeHtml(m.s) + '</code></div>';
    }

    // Description
    if(m.d){
      html += '<div class="mi-doc">' + escapeHtml(cleanText(m.d)) + '</div>';
    }

    // Parameters
    if(m.p && m.p.length > 0){
      html += '<div class="mi-params">';
      html += '<div class="mi-section-title">参数</div>';
      m.p.forEach(function(p){
        html += '<div class="mi-param">';
        html += '<div class="mi-param-row">';
        html += '<span class="mi-param-name">' + escapeHtml(p[0]) + '</span>';
        if(p[2]) html += renderTypeSpan(p[2]);
        html += '</div>';
        if(p[1]) html += '<div class="mi-param-desc">' + escapeHtml(cleanText(p[1])) + '</div>';
        html += '</div>';
      });
      html += '</div>';
    }

    // Returns
    if(m.r || m.rt || (m.rc && m.rc.length > 0)){
      html += '<div class="mi-returns">';
      html += '<div class="mi-section-title">返回值</div>';
      if(m.rt){
        html += '<div class="mi-returns-row"><span class="mi-returns-label">类型</span> ' + renderTypeSpan(m.rt) + '</div>';
      }
      if(m.r){
        html += '<div class="mi-returns-row"><span class="mi-returns-label">说明</span> <span class="mi-param-desc">' + escapeHtml(cleanText(m.r)) + '</span></div>';
      }
      // Return components (tuple members)
      if(m.rc && m.rc.length > 0){
        html += '<div class="mi-returns-components">';
        html += '<div class="mi-returns-comp-title">返回值组成</div>';
        m.rc.forEach(function(rc){
          html += '<div class="mi-param">';
          html += '<div class="mi-param-row">';
          html += '<span class="mi-param-name">' + escapeHtml(rc[0]) + '</span>';
          if(rc[1]) html += renderTypeSpan(rc[1]);
          html += '</div>';
          if(rc[2]) html += '<div class="mi-param-desc">' + escapeHtml(cleanText(rc[2])) + '</div>';
          html += '</div>';
        });
        html += '</div>';
      }
      html += '</div>';
    }

    // Version
    if(m.v){
      html += '<div class="mi-version"><span class="mi-version-tag">🏷️ NX ' + escapeHtml(m.v) + '</span></div>';
    }

    // License
    if(m.lc && m.lc !== 'None' && m.lc !== 'None.'){
      html += '<div class="mi-license"><span class="mi-license-tag">🔑 ' + escapeHtml(m.lc) + '</span></div>';
    }

    html += '</div>';
    return html;
  }

  // ============ Search (multi-level with type & domain filters) ============
  var searchIndex = null;
  var searchTimer = null;
  var searchFilter = {cls: true, method: true, prop: true};  // multi-select toggles
  var searchDomain = 'all';     // 'all' | domainName

  function buildSearchIndex(){
    var items = [];
    DATA.forEach(function(d){
      d.mods.forEach(function(m){
        m.c.forEach(function(c){
          items.push({type:'class', tname:'类', name:c[0].split('.').pop(), path:d.n + ' / ' + m.n, doc:c[1]||'', data:{mod:m.n, cls:c[0], domain:d.n}});
          (c[2]||[]).forEach(function(meth){
            if(!meth.n) return;
            var isProp = meth.pr === 1;
            items.push({
              type: isProp ? 'prop' : 'method',
              tname: isProp ? '属性' : '方法',
              name: meth.n,
              path: d.n + ' / ' + m.n + ' / ' + c[0].split('.').pop(),
              doc: meth.d || '',
              data: {mod: m.n, cls: c[0], method: meth.n, domain: d.n}
            });
          });
        });
      });
    });
    searchIndex = items;
  }

  setTimeout(buildSearchIndex, 200);

  var searchInput = document.getElementById('search-input');
  var searchResults = document.getElementById('search-results');
  var searchClear = document.getElementById('search-clear');

  function matchScore(name, path, q){
    var nl = name.toLowerCase();
    var pl = path.toLowerCase();
    var score = 0;
    if(nl === q) score = 1000;                    // exact match
    else if(nl.indexOf(q) === 0) score = 800;     // prefix match
    else if(nl.indexOf(q) > 0){
      // word-boundary match (preceded by uppercase or separator)
      var idx = nl.indexOf(q);
      var before = nl[idx-1];
      if(before === '.' || before === '_' || before === ' ' || (before && before === before.toUpperCase() && before !== before.toLowerCase())){
        score = 500;                              // word-boundary match
      } else {
        score = 200;                              // substring match in name
      }
    }
    if(score === 0 && pl.indexOf(q) >= 0) score = 50;  // path-only match
    // shorter name = more relevant, add small bonus
    if(score > 0) score += Math.max(0, 100 - name.length);
    return score;
  }

  function doSearch(){
    var q = searchInput.value.trim().toLowerCase();
    if(!q){ searchResults.classList.remove('show'); return; }
    if(!searchIndex) return;
    var allClassMatches = [];
    var allMethodMatches = [];
    var allPropMatches = [];
    for(var i=0; i<searchIndex.length; i++){
      var item = searchIndex[i];
      if(searchDomain !== 'all' && item.data.domain !== searchDomain) continue;
      var score = matchScore(item.name, item.path, q);
      if(score === 0) continue;
      item._score = score;
      if(item.type === 'class'){
        allClassMatches.push(item);
      } else if(item.type === 'prop'){
        allPropMatches.push(item);
      } else {
        allMethodMatches.push(item);
      }
    }
    // Sort by score descending, take top N
    allClassMatches.sort(function(a,b){ return b._score - a._score; });
    allMethodMatches.sort(function(a,b){ return b._score - a._score; });
    allPropMatches.sort(function(a,b){ return b._score - a._score; });
    allClassMatches = allClassMatches.slice(0, 100);
    allMethodMatches = allMethodMatches.slice(0, 150);
    allPropMatches = allPropMatches.slice(0, 100);
    renderSearchResults(allClassMatches, allMethodMatches, allPropMatches);
  }
  function renderSearchResults(classMatches, methodMatches, propMatches){
    var totalClass = classMatches.length;
    var totalMethod = methodMatches.length;
    var totalProp = propMatches.length;
    var total = totalClass + totalMethod + totalProp;
    if(total === 0){
      searchResults.innerHTML = '<div class="sr-empty">\u672a\u627e\u5230\u5339\u914d\u7ed3\u679c</div>';
      searchResults.classList.add('show');
      return;
    }
    var html = '<div class="sr-filters">';
    html += '<span class="sr-tab ' + (searchFilter.cls ? 'active' : '') + '" data-filter="cls">\u7c7b<span class="sr-count">' + totalClass + '</span></span>';
    html += '<span class="sr-tab ' + (searchFilter.method ? 'active' : '') + '" data-filter="method">\u65b9\u6cd5<span class="sr-count">' + totalMethod + '</span></span>';
    html += '<span class="sr-tab ' + (searchFilter.prop ? 'active' : '') + '" data-filter="prop">\u5c5e\u6027<span class="sr-count">' + totalProp + '</span></span>';
    html += '<select class="sr-domain-sel" id="sr-domain">';
    html += '<option value="all"' + (searchDomain==='all'?' selected':'') + '>\u5168\u90e8\u529f\u80fd\u57df</option>';
    DATA.forEach(function(d){
      html += '<option value="' + escapeAttr(d.n) + '"' + (searchDomain===d.n?' selected':'') + '>' + escapeHtml(d.n) + '</option>';
    });
    html += '</select>';
    html += '</div>';
    html += '<div class="sr-list">';
    if(searchFilter.cls && classMatches.length > 0){
      html += '<div class="sr-group-header">\u7c7b (' + totalClass + ')</div>';
      classMatches.forEach(function(m){ html += renderSearchItem(m); });
    }
    if(searchFilter.method && methodMatches.length > 0){
      html += '<div class="sr-group-header">\u65b9\u6cd5 (' + totalMethod + ')</div>';
      methodMatches.forEach(function(m){ html += renderSearchItem(m); });
    }
    if(searchFilter.prop && propMatches.length > 0){
      html += '<div class="sr-group-header">\u5c5e\u6027 (' + totalProp + ')</div>';
      propMatches.forEach(function(m){ html += renderSearchItem(m); });
    }
    if(!searchFilter.cls && !searchFilter.method && !searchFilter.prop){
      html += '<div class="sr-empty">\u8bf7\u81f3\u5c11\u9009\u62e9\u4e00\u4e2a\u6807\u7b7e</div>';
    }
    if(totalClass >= 100 || totalMethod >= 150 || totalProp >= 100){
      html += '<div class="sr-empty" style="padding:8px">\u7ed3\u679c\u8fc7\u591a\uff0c\u8bf7\u8f93\u5165\u66f4\u7cbe\u786e\u7684\u5173\u952e\u8bcd</div>';
    }
    html += '</div>';
    searchResults.innerHTML = html;
    searchResults.classList.add('show');
  }
  function renderSearchItem(m){
    var tagColor = m.type === 'class' ? '#58a6ff' : (m.type === 'prop' ? '#bc8cff' : '#79c0ff');
    var html = '<div class="search-item" data-mod="' + escapeAttr(m.data.mod) + '" data-cls="' + escapeAttr(m.data.cls) + '" data-method="' + (m.data.method ? escapeAttr(m.data.method) : '') + '">';
    html += '<div class="si-name"><span class="si-tag" style="color:' + tagColor + '">[' + m.tname + ']</span>' + escapeHtml(m.name) + '</div>';
    html += '<div class="si-path">' + escapeHtml(m.path) + '</div>';
    if(m.doc) html += '<div class="si-doc">' + escapeHtml(cleanText(m.doc).substring(0,100)) + '</div>';
    html += '</div>';
    return html;
  }
  // Filter tab clicks (delegated)
  searchResults.addEventListener('click', function(e){
    var tab = e.target.closest('.sr-tab');
    if(tab){
      e.stopPropagation();
      var key = tab.dataset.filter;
      searchFilter[key] = !searchFilter[key];
      doSearch();
      return;
    }
    if(e.target.id === 'sr-domain'){
      return;
    }
    var item = e.target.closest('.search-item');
    if(!item || !item.dataset.mod) return;
    var modName = item.dataset.mod;
    var clsName = item.dataset.cls;
    var methodName = item.dataset.method;
    var domain = findDomain(modName);
    if(!domain) return;
    var mod = domain.mods.find(function(m){ return m.n === modName; });
    if(!mod) return;
    var cls = mod.c.find(function(c){ return c[0] === clsName; });
    if(!cls) return;
    showClassDetail(mod, cls);
    searchResults.classList.remove('show');
    if(methodName){
      setTimeout(function(){
        var items = detailPanel.querySelectorAll('.method-item');
        items.forEach(function(mi){
          var nameEl = mi.querySelector('.mi-name');
          if(nameEl && nameEl.textContent.indexOf(methodName) === 0){
            mi.style.border = '2px solid #58a6ff';
            mi.scrollIntoView({behavior:'smooth', block:'center'});
          }
        });
      }, 100);
    }
  });

  // Input handler (debounced)
  searchInput.addEventListener('input', function(){
    var q = searchInput.value.trim();
    searchClear.style.display = q ? 'block' : 'none';
    clearTimeout(searchTimer);
    if(!q){ searchResults.classList.remove('show'); return; }
    searchTimer = setTimeout(doSearch, 200);
  });
  // Enter key — trigger search immediately
  searchInput.addEventListener('keydown', function(e){
    if(e.key === 'Enter'){
      e.preventDefault();
      clearTimeout(searchTimer);
      var q = searchInput.value.trim();
      if(q) doSearch();
    }
  });

  // Domain dropdown change
  searchResults.addEventListener('change', function(e){
    if(e.target.id === 'sr-domain'){
      e.stopPropagation();
      searchDomain = e.target.value;
      doSearch();
    }
  });

  searchClear.addEventListener('click', function(){
    searchInput.value = '';
    searchClear.style.display = 'none';
    searchResults.classList.remove('show');
    searchInput.focus();
  });

  document.addEventListener('click', function(e){
    if(!e.target.closest('.search-box')) searchResults.classList.remove('show');
  });

  // ============ Utils ============
  function findDomain(modName){
    for(var di=0; di<DATA.length; di++){
      for(var mi=0; mi<DATA[di].mods.length; mi++){
        if(DATA[di].mods[mi].n === modName) return DATA[di];
      }
    }
    return null;
  }
  // ============ Type resolver: resolve NXOpen type string to (mod, fullClass) ============
  var _typeShortMap = null;
  function buildTypeShortMap(){
    if(_typeShortMap) return _typeShortMap;
    _typeShortMap = {};
    DATA.forEach(function(d){
      d.mods.forEach(function(mo){
        mo.c.forEach(function(cls){
          var short = cls[0].split('.').pop();
          if(!_typeShortMap[short]) _typeShortMap[short] = [];
          _typeShortMap[short].push([mo.n, cls[0]]);
        });
      });
    });
    return _typeShortMap;
  }
  function resolveTypeToClass(typeStr){
    if(!typeStr) return null;
    var clean = typeStr.replace(':py:class: ', '').trim();
    if(clean.indexOf('list of ') === 0) clean = clean.substring(8);
    if(clean.indexOf('NXOpen.') !== 0) return null;
    var relative = clean.substring(7);
    var junkIdx = relative.search(/[ ;,]/);
    if(junkIdx > 0) relative = relative.substring(0, junkIdx);
    var parts = relative.split('.');
    var className = parts[parts.length - 1];
    if(!className) return null;
    if({'bool':1,'int':1,'float':1,'str':1,'list':1,'dict':1,'tuple':1,'object':1,'None':1}[className]) return null;
    if(parts.length >= 2){
      var modCandidate = parts[0];
      var dom = findDomain(modCandidate);
      if(dom){
        var mod = null;
        for(var i=0; i<dom.mods.length; i++){
          if(dom.mods[i].n === modCandidate){ mod = dom.mods[i]; break; }
        }
        if(mod){
          var targetFull = modCandidate + '.' + relative;
          for(var j=0; j<mod.c.length; j++){
            if(mod.c[j][0] === targetFull) return [modCandidate, targetFull];
          }
          for(var j=0; j<mod.c.length; j++){
            if(mod.c[j][0].split('.').pop() === className) return [modCandidate, mod.c[j][0]];
          }
        }
      }
    }
    var sm = buildTypeShortMap();
    var candidates = sm[className];
    if(candidates && candidates.length > 0){
      return candidates[0];
    }
    return null;
  }
  function renderTypeSpan(typeStr){
    var resolved = resolveTypeToClass(typeStr);
    if(resolved){
      var clean = typeStr.replace(':py:class: ', '').trim();
      if(clean.indexOf('list of ') === 0) clean = clean.substring(8);
      var prefix = typeStr.indexOf('list of ') === 0 ? 'list of ' : '';
      return '<span class="mi-param-type type-link" data-mod="' + escapeAttr(resolved[0]) + '" data-cls="' + escapeAttr(resolved[1]) + '" title="' + escapeAttr(resolved[1]) + '">' + escapeHtml(prefix + clean) + '</span>';
    }
    return '<span class="mi-param-type">' + escapeHtml(typeStr) + '</span>';
  }

  function escapeHtml(s){
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  }
  function escapeAttr(s){
    return String(s).replace(/"/g,'&quot;').replace(/'/g,'&#39;');
  }
  function cleanText(s){
    if(!s) return '';
    return String(s).replace(/\\'/g, "'").replace(/\\"/g, '"').replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim();
  }

  // ============ Resizer (drag to resize left/right panels) ============
  (function(){
    var resizer = document.getElementById('resizer');
    var mindmapPanel = document.querySelector('.mindmap-panel');
    var mainEl = document.querySelector('.main');
    var dragging = false;

    resizer.addEventListener('mousedown', function(e){
      e.preventDefault();
      dragging = true;
      resizer.classList.add('dragging');
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    });

    document.addEventListener('mousemove', function(e){
      if(!dragging) return;
      var rect = mainEl.getBoundingClientRect();
      var pct = ((e.clientX - rect.left) / rect.width) * 100;
      if(pct < 15) pct = 15;       // min 15%
      if(pct > 85) pct = 85;       // max 85%
      mindmapPanel.style.flexBasis = pct + '%';
      // Trigger SVG resize
      if(typeof fitScreen === 'function' && !d3.event) {
        // Don't auto-fit during drag; let user release first
      }
    });

    document.addEventListener('mouseup', function(){
      if(!dragging) return;
      dragging = false;
      resizer.classList.remove('dragging');
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
      // Resize SVG to match new container
      if(svgEl && svgNode){
        var w = svgNode.clientWidth;
        var h = svgNode.clientHeight;
        svgEl.attr('width', w).attr('height', h);
        tree.nodeSize([36, 200]);  // keep consistent spacing, don't cram into viewport
        update(treeRoot);
      }
    });
  })();

  // ============ Init ============
  treeRoot.children.slice(0,1).forEach(function(d){ d._collapsed = true; });
  update(treeRoot);
  setTimeout(fitScreen, 100);
})();
